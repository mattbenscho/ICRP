# -*- coding: utf-8 -*-

"""
Anki Add-on: Integrated Chinese Reading Practice

Integrates your reading practice with your character reviews.

TODO:
- Move hardcoded strings/values to settings

Copyright: (c) 2019 Matthias B. Schönborn <mattbenscho@gmail.com>
"""

from aqt.reviewer import Reviewer
from aqt.utils import tooltip
from aqt import mw
from anki.hooks import wrap
import json
import os
from collections import defaultdict
from aqt.qt import *
from anki.hooks import addHook
from datetime import date, datetime
import math # for math.ceil
import random
from anki.lang import _
import sys # for recursionlimit

sys.setrecursionlimit(100000)

def ICRP_LinkHandler(reviewer, url):
    global log_message
    global character_translations_cache
    day_zero = int(mw.col.crt / (24*3600))
    if url.startswith("ICRP"):
        # fail any card for the character
        character = url[4:]
        ids = mw.col.findCards("hanzi:{}".format(character))
        if len(ids) > 0:
            # tooltip(character)
            for card_id in ids:
                card = mw.col.getCard(card_id)
                if card.type == 2:
                    oldivl = card.ivl
                    newivl = math.ceil(0.1 * oldivl)
                    card.ivl = newivl
                    card.due = int(datetime.now().timestamp() / (24*3600)) - day_zero
                    card.flush()        
                    message = "Rescheduled hanzi card for {}. Old ivl was {}, new ivl is {}.".format(character, oldivl, newivl)
                    print(message)
                    log_message += message + "\n"
                    note = card.note()
                    translations = note["translations"] # print(note["components"])            
                    character_translations_cache = translations + character_translations_cache
                    element = "document.getElementById(\"cache\")"
                    jsondump = json.dumps(character_translations_cache)
                    mw.web.eval("{}.innerHTML = {};".format(element, jsondump))

        reschedule_sentences(reviewer, character = character)
    else:
        origLinkHandler(reviewer, url)

def read_cedict():
    addon_path = os.path.dirname(__file__)
    with open(addon_path + "/cedict_1_0_ts_utf-8_mdbg.txt") as f:
        cedict_lines = f.readlines()

    cedict_lines = [x.strip() for x in cedict_lines]
    list_dict = defaultdict(list)
    for cl in cedict_lines:
        if cl.startswith("#"):
            continue

        traditional = cl.split(" ")[0]
        simplified = cl.split(" ")[1]
        pinyin = cl.split('[', 1)[1].split(']')[0]
        translations = list(filter(None, cl.split("/")[1:]))
        list_dict[traditional].append([simplified, pinyin, translations])
        if traditional != simplified:
            list_dict[simplified].append([traditional, pinyin, translations])
        # print([traditional, simplified, pinyin, translations])

    return list_dict

def update_character_notes():
    global log_message
    tooltip("Updating Chinese character notes to add examples... ")
    ids = mw.col.findCards("note:Hanzi")
    for card_id in ids:
        card = mw.col.getCard(card_id)
        note = card.note()
        hanzi = note["hanzi"]
        print(hanzi)
        examples = ""
        sentence_ids = mw.col.findCards("note:Sentence Sentence:\"*{}*\" -is:suspended".format(hanzi))
        if len(sentence_ids) > 7:
            indices = random.sample(range(len(sentence_ids)), 7)
            sentence_ids = [sentence_ids[i] for i in sorted(indices)]

        for sentence_id in sentence_ids:
            sentence_card = mw.col.getCard(sentence_id)
            # print(sentence_card.note()["Sentence"])
            example = sentence_card.note()["Sentence with pinyin"]
            example = example.replace(hanzi, "<span class=\"highlight\">{}</span>".format(hanzi))
            examples += "<div class=\"example_sentence\">"
            examples += "<div class=\"example_zh\">{}</div>".format(example)
            examples += "<div class=\"example_en\">{}</div>".format(sentence_card.note()["Translation"])
            examples += "</div>"

        note["examples"] = examples
        note.flush()
            
    message = "Update complete!"
    print(message)
    log_message += message + "\n"

def update_ICRP_sentences():
    global log_message
    tooltip("Updating ICRP sentences... ")
    chinese_dictionary = read_cedict()
    cedict_keys = list(chinese_dictionary.keys())

    # get all seen Chinese characters:
    ids = mw.col.findCards("note:Hanzi -is:suspended -is:new")
    known_hanzis = []
    for card_id in ids:
        hanzi = mw.col.getCard(card_id).note()["hanzi"]
        known_hanzis.append(hanzi)
    # print(known_hanzis)

    # get all seen Chinese words:
    ids = mw.col.findCards("note:Word -is:suspended -is:new")
    known_words = []
    for card_id in ids:
        word = mw.col.getCard(card_id).note()["hanzis"]
        known_words.append(word)
    # print(known_words)

    # iterate over the ICRP sentences:
    ids = mw.col.findCards("note:Sentence")
    for card_id in ids:
        table = "<table>\n"
        card = mw.col.getCard(card_id)
        note = card.note()

        # assigning vocabulary:
        sentence = note["Sentence"]
        print(sentence)
        while len(sentence) > 0:
            end_index = len(sentence)
            while end_index > 0:
                part = sentence[0:end_index]
                result = chinese_dictionary[part]
                if len(result) > 0:
                    ktag = ""
                    if end_index > 1:
                        if part in known_words:
                            ktag = " class=\"known\""
                    else:
                        if part in known_hanzis:
                            ktag = " class=\"known\""
                    for entry in result:
                        table += "<tr{}>".format(ktag)
                        if part != entry[0]:
                            table += "<td class=\"hanzi small\">{}({})</td>".format(part, entry[0])
                        else:
                            table += "<td class=\"hanzi small\">{}</td>".format(part)
                        table += "<td class=\"pinyin\">{}</td>".format(entry[1])
                        table += "<td class=\"translation\">{}</td>".format((" / ").join(entry[2]))
                        table += "</tr>\n"
                end_index -= 1
            sentence = sentence[1:]
        table += "</table>"
        note["Vocabulary"] = table
        note.flush()

        # creating {{Sentence with pinyin}}:        
        sentence = note["Sentence"]
        sentence_with_pinyin = ""
        for character in sentence:
            pinyins = []
            if character in known_hanzis:
                ktag = " known"
            else:
                ktag = ""                            
            result = chinese_dictionary[character]
            for entry in result:
                pinyins.append(entry[1])
            color = list(set([ x[-1] for x in pinyins ]))
            if len(color) == 1:
                color_class = " color{}".format(color[0])
            else:
                color_class = ""
            sentence_with_pinyin += "<div class=\"hanzi_with_pinyin{}\">".format(ktag)
            sentence_with_pinyin += "<div class=\"hanzi{}\">{}</div>".format(color_class, character)
            uniqe_pinyins = sorted(list(set([ x.lower() for x in pinyins ])))
            pinyin_divs = ("").join([ "<div class=\"pinyin_div color{}\">{}</div>".format(x[-1], x) for x in uniqe_pinyins ])
            sentence_with_pinyin += "<div class=\"pinyins_div\">{}</div></div>\n".format(pinyin_divs)
        note["Sentence with pinyin"] = sentence_with_pinyin
        note.flush()

    tooltip("Update complete!")
    return

def clear_cache(reviewer, ease = None):
    global character_translations_cache
    character_translations_cache = ""
    # print("cleared cache in clear_cache")

def load_cache(reviewer):
    global character_translations_cache
    element = "document.getElementById(\"cache\")"
    mw.web.eval("try {{ {}.innerHTML = {} }} catch(e) {{}};".format(element, json.dumps(character_translations_cache)))

def print_log_message(reviewer, ease = None):
    global log_message
    if len(log_message) > 0:
        tooltip(log_message)
        log_message = ""

def reschedule_sentences(reviewer, ease = None, character = None):
    # Reschedule up to n random sentences with the character to be due today.
    # If there is no character passed in the function variables,
    # we try to get one from the current card.
    # In this case we also need to check the ease.

    global log_message    
    day_zero = int(mw.col.crt / (24*3600))
    
    if not character:
        note = mw.reviewer.card.note()
        if "hanzi" in note.keys():
            character = note["hanzi"]

    if character and (ease == 1 or ease == None):
        ids = mw.col.findCards("Sentence:*{}* -is:suspended -is:new".format(character))
        if len(ids) > 0:
            random.shuffle(ids)
            due_date_in_days = int(datetime.now().timestamp() / (24*3600)) - day_zero
            current_id = mw.reviewer.card.id
            if len(ids) == 1 and ids[0] == current_id:
                message = "There are no other example sentences containing \"{}\".".format(character)
                print(message)
                log_message += message + "\n"
            else:
                if len(ids) > 7: # TODO: customize number
                    ids = ids[:7]
                if current_id in ids:
                    rescheduled_count = len(ids) - 1
                else:
                    rescheduled_count = len(ids)
                for card_id in ids:
                    card = mw.col.getCard(card_id)
                    if card.type == 2 and not card_id == current_id:
                        oldivl = card.ivl
                        card.due = due_date_in_days
                        newivl = math.ceil(0.1 * oldivl)
                        card.ivl = newivl
                        message = "Sentence: old ivl was {}, new ivl is {}.".format(oldivl, newivl)
                        print(message)
                        # log_message = message + "\n"
                        card.flush()

                message = "Rescheduled {} sentences for {}.".format(rescheduled_count, character)
                print(message)
                log_message += message + "\n"
                        
def reschedule_elements_and_appearances(reviewer, ease = None):
    global log_message
    global due_characters
    day_zero = int(mw.col.crt / (24*3600))
    note = mw.reviewer.card.note()
    if "hanzi" in note.keys() and "elements" in note.keys() and "appearances" in note.keys():
        character = note["hanzi"]
        elements = note["elements"]
        appearances = note["appearances"]
        hanzis = elements + appearances
        due_characters = ""
        # print(", ".join([character, elements, appearances, hanzis]))

    rescheduled = ""
    card = mw.reviewer.card
    if character and hanzis and (ease == 1 or ease == None) and card.type != 0 and card.queue != 0:
        searchstring = " or ".join([ "hanzi:"+i for i in hanzis ])
        ids = mw.col.findCards("({}) -is:suspended -is:new deck:\"MandarinBanana Hanzis\"".format(searchstring))
        if len(ids) > 0:            
            due_date_in_days = int(datetime.now().timestamp() / (24*3600)) - day_zero
            current_id = mw.reviewer.card.id
            for card_id in ids:
                card = mw.col.getCard(card_id)
                if card.type == 2:
                    oldivl = card.ivl
                    card.due = due_date_in_days
                    newivl = math.ceil(0.1 * oldivl)
                    card.ivl = newivl
                    note = card.note()
                    rescheduled += note["hanzi"]
                    message = "{}({}->{});".format(note["hanzi"], oldivl, newivl)
                    print(message)
                    # log_message += message + " \n"
                    card.flush()

            log_message += "Rescheduled {}; ".format(rescheduled)
    
def bury_due_to_component(reviewer, ease = None):
    global log_message
    global due_characters
    global do_mw_reset
    day_zero = int(mw.col.crt / (24*3600))
    today_in_days = int(datetime.now().timestamp() / (24*3600)) - day_zero

    # first we need to get the list with due characters if its empty:
    if due_characters == "":
        # print("Getting due characters... ")
        due_cards = mw.col.findCards("deck:\"MandarinBanana Hanzis\" is:due -is:suspended -is:new")
        for due_id in due_cards:
            due_card = mw.col.getCard(due_id)
            due_note = due_card.note()
            due_characters += due_note["hanzi"]
    
    note = mw.reviewer.card.note()
    if "hanzi" in note.keys() and "elements" in note.keys():
        character = note["hanzi"]
        elements = note["elements"]
        for element in elements:
            if element in due_characters:
                # bury the current note, because one of its elements is due.
                # Anki will pull out a new card after the mw.reset().
                mw.checkpoint(_("Bury"))
                mw.col.sched.buryNote(mw.reviewer.card.nid)
                message = "Buried {} due to {}.".format(character, element)
                print(message)
                do_mw_reset = True
                # print("do_mw_reset in bury_due_to_component = {}".format(do_mw_reset))
                # mw.reset()
                break

def execute_mw_reset(reviewer, ease = None):
    global do_mw_reset
    # print("do_mw_reset in execute_mw_reset = {}".format(do_mw_reset))
    if do_mw_reset == True:
        # print("Executing a MW reset now!")
        do_mw_reset = False
        mw.reset()

# Global variables
character_translations_cache = ""
log_message = ""
due_characters = ""
do_mw_reset = False

origLinkHandler = Reviewer._linkHandler
Reviewer._linkHandler = ICRP_LinkHandler

Reviewer._showQuestion = wrap(Reviewer._showQuestion, execute_mw_reset, "after")
Reviewer._showQuestion = wrap(Reviewer._showQuestion, bury_due_to_component, "before")
Reviewer._showQuestion = wrap(Reviewer._showQuestion, clear_cache, "before")
Reviewer._answerCard = wrap(Reviewer._answerCard, clear_cache, "before")
Reviewer._answerCard = wrap(Reviewer._answerCard, reschedule_sentences, "before")
Reviewer._answerCard = wrap(Reviewer._answerCard, reschedule_elements_and_appearances, "before")
Reviewer._answerCard = wrap(Reviewer._answerCard, print_log_message, "after")
Reviewer._showAnswer = wrap(Reviewer._showAnswer, load_cache)

update_ICRP_sentences_action = QAction("Update ICRP sentences", mw)
update_ICRP_sentences_action.triggered.connect(update_ICRP_sentences)
mw.form.menuTools.addAction(update_ICRP_sentences_action)

update_character_notes_action = QAction("Update Chinese character notes", mw)
update_character_notes_action.triggered.connect(update_character_notes)
mw.form.menuTools.addAction(update_character_notes_action)
