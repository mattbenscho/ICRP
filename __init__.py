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

def ICRP_LinkHandler(reviewer, url):
    global character_translations_cache
    day_zero = int(mw.col.crt / (24*3600))
    if url.startswith("ICRP"):
        # fail any card for the character
        character = url[4:]
        ids = mw.col.findCards("hanzi:{}".format(character))
        if len(ids) > 0:
            # tooltip(character)
            for id in ids:
                card = mw.col.getCard(id)
                if card.type == 2:
                    oldivl = card.ivl
                    newivl = math.ceil(0.1 * oldivl)
                    card.ivl = newivl
                    card.due = int(datetime.now().timestamp() / (24*3600)) - day_zero
                    card.flush()        
                    message = "Rescheduled hanzi card for {}. Old ivl was {}, new ivl is {}.".format(character, oldivl, newivl)
                    tooltip(message)
                    print(message)
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
    tooltip("Updating Chinese character notes to add examples... ")
    ids = mw.col.findCards("note:Hanzi")
    for id in ids:
        card = mw.col.getCard(id)
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
    tooltip(message)
    print(message)

def update_ICRP_sentences():
    tooltip("Updating ICRP sentences... ")
    chinese_dictionary = read_cedict()
    cedict_keys = list(chinese_dictionary.keys())

    # get all seen Chinese characters:
    ids = mw.col.findCards("note:Hanzi -is:suspended -is:new")
    known_hanzis = []
    for id in ids:
        hanzi = mw.col.getCard(id).note()["hanzi"]
        known_hanzis.append(hanzi)
    # print(known_hanzis)

    # get all seen Chinese words:
    ids = mw.col.findCards("note:Word -is:suspended -is:new")
    known_words = []
    for id in ids:
        word = mw.col.getCard(id).note()["hanzis"]
        known_words.append(word)
    # print(known_words)

    # iterate over the ICRP sentences:
    ids = mw.col.findCards("note:Sentence")
    for id in ids:
        table = "<table>\n"
        card = mw.col.getCard(id)
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

def reschedule_sentences(reviewer, ease = None, character = None):
    # Reschedule up to n random sentences with the character to be due today.
    # If there is no character passed in the function variables,
    # we try to get one from the current card.
    # In this case we also need to check the ease.
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
            if len(ids) > 7: # TODO: customize number
                ids = ids[:7]
            for id in ids:
                card = mw.col.getCard(id)
                if card.type == 2:
                    oldivl = card.ivl
                    card.due = due_date_in_days
                    newivl = math.ceil(0.1 * oldivl)
                    card.ivl = newivl
                    print("Old ivl was {}, new ivl is {}.".format(oldivl, newivl))
                    card.flush()
            message = "Rescheduled {} sentences for {}.".format(len(ids), character)
            tooltip(message)
            print(message)
    

character_translations_cache = ""

origLinkHandler = Reviewer._linkHandler
Reviewer._linkHandler = ICRP_LinkHandler

Reviewer._showQuestion = wrap(Reviewer._showQuestion, clear_cache, "before")
Reviewer._answerCard = wrap(Reviewer._answerCard, clear_cache, "before")
Reviewer._answerCard = wrap(Reviewer._answerCard, reschedule_sentences, "before")
Reviewer._showAnswer = wrap(Reviewer._showAnswer, load_cache)

update_ICRP_sentences_action = QAction("Update ICRP sentences", mw)
update_ICRP_sentences_action.triggered.connect(update_ICRP_sentences)
mw.form.menuTools.addAction(update_ICRP_sentences_action)

update_character_notes_action = QAction("Update Chinese character notes", mw)
update_character_notes_action.triggered.connect(update_character_notes)
mw.form.menuTools.addAction(update_character_notes_action)
