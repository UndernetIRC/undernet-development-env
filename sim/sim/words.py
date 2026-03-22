from __future__ import annotations

import random

GIBBERISH_WORDS = [
    "blorpz", "snazzle", "wibwomp", "flonk", "grizzbit",
    "zeptoflux", "morkle", "quagnash", "splunt", "fizzgig",
    "nubwort", "crumple", "dingbat", "flimflam", "gobsmack",
    "hootzpa", "jibber", "kerfuffle", "lollygag", "mumblecrust",
    "noodlezap", "pizzazz", "quibble", "razzmatazz", "skedaddle",
    "troglodyte", "bumfuzzle", "cattywampus", "dingleberry", "flibbertigibbet",
    "gazump", "hoodwink", "iglooze", "jalopy", "kumquat",
    "lampoon", "malarkey", "nincompoop", "oompaloopa", "persnickety",
    "quagmire", "rigmarole", "slapdash", "tomfoolery", "ululate",
    "voodoodle", "wackadoo", "xylophonk", "yabbadoo", "zigzagoon",
    "blunderbuss", "codswallop", "donnybrook", "fractalplop", "gibberjab",
    "hullabaloo", "ipsydoodle", "janglefrap", "kablooey", "snarfblatt",
]

TEMPLATES = [
    "i think {w1} is way more {w2} than {w3}",
    "has anyone seen my {w1}? i left it near the {w2}",
    "lol {w1} {w2} {w3}",
    "{w1}!!! {w2}!!!",
    "just got back from the {w1} convention, it was {w2}",
    "why does {w1} always {w2} when you {w3}",
    "brb gotta {w1} my {w2}",
    "tbh the whole {w1} situation is pretty {w2}",
    "anyone wanna {w1}? i got extra {w2}",
    "{w1} or {w2}? discuss.",
    "imagine being a {w1} in this economy",
    "my {w1} just {w2}ed all over the {w3}",
    "hot take: {w1} > {w2}",
    "ok but what if we {w1} the {w2} instead",
    "breaking: local {w1} discovers {w2}, more at 11",
    "ngl that {w1} was kinda {w2}",
    "the {w1} of {w2} is strong with this one",
    "pro tip: never {w1} a {w2} on a tuesday",
    "just vibing with some {w1} and {w2}",
    "friendly reminder to {w1} your {w2} daily",
]


def generate_message() -> str:
    template = random.choice(TEMPLATES)
    words = random.sample(GIBBERISH_WORDS, 3)
    return template.format(w1=words[0], w2=words[1], w3=words[2])
