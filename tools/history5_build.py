"""Builds scripts/queue/_history5.json from Rakib's approved script (narration only).

Each entry is one scene: (say with v3 tags, beats). A beat is (at_word, query) for footage,
or a dict for a title card / number. "part" marks where a new ElevenLabs read starts;
"music" marks where a new music part starts.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TAG = re.compile(r"\[[A-Za-z][A-Za-z ]{0,24}\]")


def card(text, query):
    return {"shot": "text", "text": text, "query": query, "camera": "drift", "transition": "fade", "sfx": ["shimmer"]}


def num(to, suffix, label, query, dec=0):
    return {"shot": "number", "query": query, "camera": "drift", "transition": "zoom", "sfx": ["whoosh", "tick"],
            "number": {"from": 0, "to": to, "suffix": suffix, "label": label, "prefix": "", "decimals": dec}}


S = []  # (say, beats, part, music)


def sc(say, *beats, part=False, music=None, hi=None):
    S.append((say, list(beats), part, music, hi or []))


# ---------------- Hook
sc("[serious] March 1974.", (0, card("MARCH 1974", "dense jungle trees")), part=True, music="investigations.mp3")
sc("A Japanese soldier walks out of the jungle in a tattered uniform.", (0, "soldier walking jungle"), (7, "dense jungle trees"))
sc("His rifle still works.", (0, "old rifle"), hi=["still works."])
sc("And as far as he knows... World War Two is still going on.", (0, "jungle mist"), hi=["still going on."])
sc("[curious] That really happened.", (0, "jungle sunlight"))
sc("And it's not the only story today that sounds made up.", (0, "old book pages"))
sc("[excited] An army that lost a war... to birds.", (0, "emus running"), hi=["to birds."])
sc("A town that couldn't stop dancing.", (0, "people dancing street"))
sc("A wave of syrup taller than a house.", (0, "brown liquid pouring"))
sc("[chuckles] And a man who sold the Eiffel Tower.", (0, "eiffel tower"), hi=["Eiffel Tower."])
sc("[whispers] All true. Let's start with the birds.", (0, "emu close up"))

# ---------------- Story 1: Emu War
sc("[curious] In 1932, wheat farmers in Western Australia had a big, feathery problem.",
   (0, card("WESTERN AUSTRALIA 1932", "wheat field")), (6, "wheat field farmer"), part=True, music="monkeys-spinning-monkeys.mp3",
   hi=["feathery problem."])
sc("About twenty thousand emus had marched out of the outback and into their fields, eating everything.",
   (0, num(20000, " EMUS", "MARCHING IN", "emus field")), (9, "emus walking"))
sc("So the farmers asked the government for help.", (0, "farmer worried field"))
sc("[excited] And the government sent... the army.", (0, "soldiers marching"), hi=["the army."])
sc("A major named Meredith, two machine guns, and ten thousand rounds of ammunition.",
   (0, "military officer vintage"), (5, num(10000, " ROUNDS", "OF AMMUNITION", "ammunition bullets")))
sc("[confident] On paper, this should have taken an afternoon.", (0, "clock ticking"), hi=["an afternoon."])
sc("[chuckles] It did not.", (0, "emu funny"), hi=["It did not."])
sc("The moment the guns fired, the emus scattered in every direction.", (0, "emus running"), (6, "birds scattering"))
sc("The soldiers set an ambush at a watering hole, and a huge flock walked right toward them.",
   (0, "watering hole outback"), (10, "emus flock"))
sc("They got about a dozen birds. Then the gun jammed.", (0, "emu"), (6, "machine gun"), hi=["gun jammed."])
sc("They even mounted a gun on a truck, but the ground was so rough that nobody could aim.",
   (0, "old truck dirt road"), (9, "bumpy dirt road"))
sc("After about a week, the soldiers were called home.", (0, "soldiers walking away"))
sc("Meredith later said that if he had a division with the bullet-carrying capacity of these birds,",
   (0, "emu portrait"))
sc("it could face any army in the world.", (0, "emus running field"), hi=["any army"])
sc("[curious] The farmers begged again, so the army went back for round two.", (0, "wheat field"), (7, "soldiers"),
   part=True, hi=["round two."])
sc("In the end, Meredith's report claimed nine hundred and eighty-six emus...", (0, "old typewriter report"))
sc("using nine thousand eight hundred and sixty bullets.",
   (0, {"shot": "compare", "query": "bullets", "camera": "drift", "transition": "flash", "sfx": ["impact", "tick"],
        "compare": {"left": {"label": "EMUS", "value": 986}, "right": {"label": "BULLETS", "value": 9860}, "unit": ""}}))
sc("[laughs] Exactly ten bullets per bird.", (0, "emu close up"), hi=["ten bullets"])
sc("Newspapers called it \"the Emu War.\"", (0, "old newspaper"), hi=["the Emu War.\""])
sc("And the emus? [amused] Still there. Still eating the wheat.", (0, "emus wheat"), (3, "emu eating"))
sc("The army had lost a war to birds.", (0, "emus running"), hi=["to birds."])
sc("[softly] Birds beating an army is funny.", (0, "birds flying sunset"))
sc("What happened in one European city, four centuries earlier... was not.", (0, "old european town"), hi=["was not."])

# ---------------- Story 2: Dancing plague
sc("[mysterious] July 14, 1518. Strasbourg.", (0, card("STRASBOURG 1518", "medieval town")), part=True, music="spy-glass.mp3")
sc("A woman named Frau Troffea stepped into the street and started to dance.", (0, "medieval street"), (8, "woman dancing"))
sc("No music. No reason.", (0, "empty street old town"), hi=["No reason."])
sc("She danced all day, until she collapsed.", (0, "dancing feet"))
sc("[uneasy] The next day, on swollen, bleeding feet, she danced again.", (0, "bare feet stone"), hi=["danced again."])
sc("By the end of the week, more than thirty people had joined her.", (0, "crowd dancing"))
sc("Within a month, some accounts say, four hundred.", (0, num(400, " DANCERS", "WITHIN A MONTH", "crowd dancing")))
sc("People who wanted to stop... and couldn't.", (0, "people dancing night"), hi=["and couldn't."])
sc("[curious] The city's doctors blamed \"hot blood,\" and their cure was simple: more dancing.",
   (0, "old medicine bottles"), (9, "people dancing"), part=True, hi=["more dancing."])
sc("[sighs] So the city built a stage, hired musicians, and paid people to keep the dancers moving.",
   (0, "wooden stage"), (8, "musicians playing violin"))
sc("It made everything worse.", (0, "storm clouds"), hi=["everything worse."])
sc("Some old records claim dancers collapsed and even died, though historians still argue about how many.",
   (0, "old manuscript"), (9, "candle dark"))
sc("Finally, the city changed its mind.", (0, "cathedral"))
sc("Music was banned, and the dancers were taken to a shrine in the hills to pray.", (0, "chapel hills"), (8, "candles church"))
sc("Slowly, the dancing stopped.", (0, "sunrise old town"))
sc("[whispers] So what was it? Nobody knows for sure.", (0, "fog forest"), hi=["Nobody knows"])
sc("Many historians think it was mass panic, in a city worn down by failed harvests, record grain prices, and disease.",
   (0, "dry wheat field"), (10, "grain sacks"))
sc("Fear spread from person to person, until it took over their bodies.", (0, "crowd silhouette"))
sc("[softly] A whole town, dancing, and not one of them wanted to.", (0, "medieval town night"), hi=["wanted to."])
sc("[tense] That town couldn't stop moving.", (0, "people dancing"))
sc("Four hundred years later, in Boston, something else started moving... and it weighed about thirteen thousand tons.",
   (0, "boston city"), (10, "industrial tank"), hi=["thirteen thousand tons."])

# ---------------- Story 3: Molasses flood
sc("[calm] January 15, 1919. Boston's North End.", (0, card("BOSTON 1919", "boston old street")), part=True, music="hitman.mp3")
sc("It was strangely warm for January, and the streets were full of people.", (0, "old city street people"))
sc("Near the harbor stood a giant steel tank.", (0, "boston harbor"), (4, "steel storage tank"))
sc("Fifty feet tall. Ninety feet wide.", (0, "industrial tank"))
sc("Filled with two point three million gallons of molasses.",
   (0, num(2.3, "M GALLONS", "OF MOLASSES", "molasses dripping", dec=1)))
sc("[serious] And the neighbors had noticed something. The tank leaked.", (0, "rusty metal"), (6, "liquid leaking"), hi=["The tank leaked."])
sc("Brown syrup oozed from its seams.", (0, "syrup dripping"))
sc("The company's fix? [scoffs] They painted the tank brown.", (0, "paint brush"), hi=["painted the tank brown."])
sc("[tense] Just after noon, people heard a deep rumble... then a rattling, like machine guns.",
   (0, "old street"), (8, "metal rivets"), part=True)
sc("That was the rivets bursting out of the steel.", (0, "steel rivets"), hi=["rivets bursting"])
sc("[shocked] And then the whole tank split open.", (0, "brown liquid wave"), hi=["split open."])
sc("A wave of molasses, twenty-five feet high, rolled through the streets at about thirty-five miles an hour.",
   (0, "brown liquid flowing"), (9, num(35, " MPH", "WAVE OF MOLASSES", "brown liquid flowing")))
sc("Faster than any person can run.", (0, "people running"), hi=["any person can run."])
sc("It knocked buildings off their foundations, smashed into the steel supports of the elevated railway,",
   (0, "flood damage"), (8, "elevated railway"))
sc("and swept up wagons, horses, and people.", (0, "horse cart old"))
sc("[sad] Twenty-one people died. Around a hundred and fifty were hurt.", (0, "candle memorial"), hi=["Twenty-one people died."])
sc("Rescuers struggled for days, because as the air cooled, the molasses grew thicker, trapping anyone caught inside.",
   (0, "rescue workers"), (10, "thick syrup"))
sc("[softly] Investigators found the tank had been badly built and barely tested.", (0, "blueprint"), (6, "inspection steel"))
sc("After that, engineers had to sign off on projects like this.", (0, "engineer signing"))
sc("[sighs] And locals said that for decades, on hot summer days, the neighborhood still smelled sweet.",
   (0, "summer street"), (8, "honey sweet"), hi=["smelled sweet."])
sc("[curious] That disaster came from cutting corners.", (0, "old city"))
sc("Our next one came from a very careful plan... to sell something that wasn't for sale.", (0, "paris street"),
   hi=["wasn't for sale."])

# ---------------- Story 4: Lustig
sc("[curious] In 1925, a smooth-talking con man named Victor Lustig read a small story in a Paris newspaper.",
   (0, card("PARIS 1925", "paris vintage")), (6, "man reading newspaper"), part=True, music="scheming-weasel-faster.mp3")
sc("The Eiffel Tower was rusting, and repairs were costing the city a fortune.", (0, "eiffel tower"), (5, "rust metal"))
sc("[sly] Most people saw a news story. Lustig saw a product.", (0, "newspaper"), (6, "eiffel tower night"), hi=["a product."])
sc("He had fake government letterhead made, posing as a top official from France's Ministry of Posts and Telegraphs.",
   (0, "old letter stamp"), (9, "typewriter"))
sc("Then he invited a handful of scrap metal dealers to one of the fanciest hotels in Paris.",
   (0, "scrap metal"), (9, "luxury hotel"))
sc("There, he told them a secret.", (0, "hotel room vintage"))
sc("[whispers] The city was going to tear down the Eiffel Tower and sell it for scrap.", (0, "eiffel tower"), hi=["sell it for scrap."])
sc("And it all had to stay quiet.", (0, "finger on lips"))
sc("[excited] One dealer, André Poisson, wanted the deal badly.", (0, "businessman vintage"), part=True)
sc("He was new in town and wanted to make a name for himself.", (0, "paris street"))
sc("Then Lustig hinted that government officials don't earn very much...", (0, "money cash"))
sc("So Poisson paid him a bribe, on top of the price.", (0, "money envelope"), hi=["a bribe,"])
sc("[laughs] Lustig grabbed the money and caught a train to Vienna.", (0, "money hand"), (6, "steam train"))
sc("And Poisson? He was too embarrassed to go to the police.", (0, "man embarrassed"), hi=["too embarrassed"])
sc("[chuckles] Lustig watched the newspapers. Not a word.", (0, "reading newspaper"), hi=["Not a word."])
sc("So not long after, he came back... and tried to sell the tower again.", (0, "eiffel tower"), hi=["again."])
sc("This time, a dealer did go to the police, and Lustig had to run.", (0, "police vintage"), (10, "running street"))
sc("Years later, he was caught in the United States, for printing fake money.", (0, "new york city"), (8, "money printing"))
sc("[amused] But for a few days in 1925, a scrap dealer truly believed he owned the most famous tower in the world.",
   (0, "eiffel tower sunset"), (11, "eiffel tower"), hi=["the most famous tower"])
sc("[serious] Lustig lied, and everyone believed him.", (0, "eiffel tower night"))
sc("Our last man was told the truth, again and again... and refused to believe it for twenty-nine years.",
   (0, "jungle"), (11, "jungle dark"), hi=["twenty-nine years."])

# ---------------- Story 5: Onoda
sc("[serious] In December 1944, a young Japanese officer named Hiroo Onoda was sent to Lubang, a small island in the Philippines.",
   (0, card("LUBANG ISLAND 1944", "tropical island")), (8, "tropical island aerial"), part=True, music="inspired.mp3")
sc("His orders: keep fighting, and never surrender.", (0, "soldier jungle"), hi=["never surrender."])
sc("As American forces landed, his commander, Major Yoshimi Taniguchi, made him a promise.", (0, "warships sea"), (6, "military officer"))
sc("Whatever happens, we'll come back for you.", (0, "jungle sunlight"), hi=["come back for you."])
sc("A few months later, World War Two ended. [softly] But no one came.", (0, "peace dove"), (7, "empty beach"), hi=["no one came."])
sc("Leaflets fell from planes saying the war was over. Onoda decided they were fake.", (0, "paper falling"), (10, "jungle"))
sc("Newspapers were left for him. Letters from his family. He believed none of it.", (0, "old letters"), (9, "jungle"),
   hi=["none of it."])
sc("[sighs] So he stayed hidden in the jungle with a few other soldiers, still fighting his war.", (0, "jungle hiding"), (10, "dense jungle"))
sc("[serious] And that war was real for the people of Lubang.", (0, "philippines village"), part=True)
sc("Over the years, Onoda's group killed local islanders. As many as thirty, by some accounts.", (0, "island village"), (8, "candle"))
sc("One by one, his companions were gone. By 1972, Onoda was alone.", (0, "jungle"), (7, "lonely jungle"), hi=["alone."])
sc("[curious] Then, in 1974, a young Japanese traveler named Norio Suzuki arrived.", (0, "backpacker travel"))
sc("He'd told friends he was searching for three things: Lieutenant Onoda, a panda, and the Abominable Snowman, in that order.",
   (0, "backpacker map"), (9, "panda"), (14, "snowy mountain"))
sc("[chuckles] He found the first one in four days.", (0, "jungle campfire"), hi=["in four days."])
sc("The two became friends. But Onoda still wouldn't come out.", (0, "campfire night"))
sc("He would only stop if his commanding officer ordered him to.", (0, "jungle"))
sc("[emotional] So Japan found Major Taniguchi, now an old man working in a bookshop, and flew him to the island.",
   (0, "old bookshop"), (12, "airplane flying"), part=True)
sc("On March 9, 1974, Taniguchi stood in front of Onoda and read him his final orders.", (0, "jungle clearing"))
sc("The war was over.", (0, "jungle sunrise"), hi=["The war was over."])
sc("[softly] Onoda handed over his sword and his rifle. It still worked.", (0, "sword"), (8, "old rifle"))
sc("[sad] He had fought for twenty-nine years, for a war that had ended long before.",
   (0, num(29, " YEARS", "STILL FIGHTING", "jungle"))
   , (6, "jungle mist"))
sc("[emotional] And Taniguchi had promised to come back.", (0, "sunset jungle"))
sc("Twenty-nine years later... he did.", (0, "sunrise sky"), hi=["he did."])

# ---------------- Ending
sc("[warm] So, which one got you? The emus, the dancers, the syrup wave, the con man, or the soldier?",
   (0, "sunset sky"), (5, "emus running"), (7, "people dancing"), (9, "brown liquid"), (13, "eiffel tower"), (16, "jungle"),
   part=True, music="carefree.mp3")
sc("Tell me in the comments.", (0, "typing phone"))
sc("[excited] Next time: a war shorter than a lunch break, a dead pope put on trial,", (0, "clock"), (9, "old church"))
sc("[whispers] and a man who survived two atomic bombs.", (0, "storm clouds"))
sc("[chuckles] Subscribe for more weird facts.", (0, card("SUBSCRIBE FOR MORE", "sunset sky")))

# ---------------- build
TR = ["cut", "cut", "whip_left", "cut", "slide_up", "cut", "zoom", "cut", "whip_right", "cut"]
CAM = ["push_in", "pan_left", "pull_out", "pan_right", "drift", "tilt_up", "push_in", "pan_right"]
LOOK = {"excited": "excited", "laughs": "excited", "chuckles": "excited", "amused": "excited",
        "sad": "sad", "emotional": "sad", "sighs": "sad",
        "whispers": "whisper", "softly": "whisper", "mysterious": "whisper",
        "shocked": "angry", "tense": "angry"}
scenes, parts, music = [], [], []
ti = ci = 0
for i, (say, beats, part, mus, hi) in enumerate(S):
    text = " ".join(TAG.sub("", say).split())
    toks = text.split()
    tags = [t.strip("[]").lower() for t in TAG.findall(say)]
    look = next((LOOK[t] for t in tags if t in LOOK), None)
    bl = []
    for at, b in beats:
        if isinstance(b, str):
            d = {"shot": "clip", "query": b, "camera": CAM[ci % len(CAM)]}
            ci += 1
            if at > 0:
                d["transition"] = "cut"
            else:
                d["transition"] = TR[ti % len(TR)]
                ti += 1
                if d["transition"] in ("whip_left", "whip_right"):
                    d["sfx"] = ["swish"]
                elif d["transition"] in ("slide_up", "zoom"):
                    d["sfx"] = ["whoosh"]
        else:
            d = dict(b)
        d["at_word"] = at
        assert at < len(toks), (text, at)
        bl.append(d)
    if i == 0:
        bl[0].update(camera="drift", sfx=["impact"])
    s = {"text": text, "say": say, "beats": bl, "highlight": hi}
    if look:
        s["look"] = look
    if part:
        parts.append(i)
    if mus:
        music.append([i, mus])
    scenes.append(s)
scenes[-1]["pause"] = 2.0          # the end card holds a moment

data = {"title": "5 Moments in History That Sound Fake (But Really Happened)", "format": "long", "style": "pro",
        "description": "Five true stories that sound made up: the Emu War, the Dancing Plague of 1518, the Great "
                       "Molasses Flood, the man who sold the Eiffel Tower, and Hiroo Onoda.",
        "tags": ["history", "weird history", "true stories", "emu war", "dancing plague", "molasses flood",
                 "victor lustig", "hiroo onoda", "weird facts"],
        "hashtags": ["history", "facts"], "shorts": False, "follow_line": "", "scene_pause": 0,
        "music_mood": "mysterious", "music_sections": music, "voice_parts": parts,
        "voice_cache": "assets/history5/cache", "scenes": scenes}
out = ROOT / "scripts/queue/_history5.json"
out.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
say_all = [s["say"] for s in scenes]
print(f"{len(scenes)} scenes, {len(parts)} voice parts, {sum(len(s['text'].split()) for s in scenes)} words, "
      f"{sum(len(x) for x in say_all) + len(say_all) - 1} characters with tags")
