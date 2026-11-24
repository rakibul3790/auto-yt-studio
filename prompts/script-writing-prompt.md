# স্ক্রিপ্ট লেখার প্রম্পট (Claude-কে দেওয়ার জন্য)

নিচের ধূসর বক্সের লেখাটা পুরোটা কপি করে Claude-কে পাঠাও। শুধু `[ ]` বন্ধনীর ভেতরের অংশ বদলাও
(ইংলিশেই লেখো)। Claude ইংলিশ দর্শকের জন্য ইংলিশ স্ক্রিপ্টের একটা JSON লিস্ট দেবে। সেটা GitHub-এ
`scripts/queue/` ফোল্ডারে নতুন ফাইল হিসেবে রাখো, নাম দাও `batch-01.json`, `batch-02.json`
(প্রতিবার নতুন নম্বর)।

---

```
You are the scriptwriter for my English-language YouTube channel. Write 10 new video scripts.

Channel topic: [e.g. surprising science facts explained simply]
Target audience: [e.g. curious adults in the US, UK, Canada and Australia]
Length of each video: [about 3–5 minutes] (roughly 140–160 spoken words per minute)
Tone: [e.g. friendly, clear, a little playful]
Topics already covered (skip these): [list, or "none"]

Rules:
- Natural, native-sounding English written to be spoken aloud: short sentences, no jargon
  without a quick explanation. Use American spelling unless I say otherwise.
- Every video must be original and genuinely useful or interesting. No templated
  copy-paste structure from one video to the next.
- Facts must be accurate. If you are not sure about a claim, leave it out.
- No brand, company or trademark names, and no copyrighted characters, songs or films.
- Open with a strong hook in the first 10 seconds; end with a short, natural call to subscribe.
- No emojis, bullet points, symbols or stage directions in the spoken text, because
  it is read aloud by a voice. Write numbers the way they are spoken ("three and a half thousand").
- 6–12 scenes per video, 2–4 sentences per scene.
- Titles should be curiosity-driven and searchable, under 70 characters, no clickbait lies.

Reply with ONLY one JSON list inside one code block, nothing else, in exactly this format:

[
  {
    "title": "Video title (max 70 characters, no < or > signs)",
    "description": "2–4 line description; the first line states what the viewer will learn",
    "tags": ["8–15 relevant search tags"],
    "hashtags": ["2–3", "hashtags"],
    "thumbnail_text": "2–5 punchy words for the thumbnail",
    "shorts": false,
    "scenes": [
      {
        "on_screen": "2–6 word headline shown big on screen",
        "visual": "stock photo search words, e.g. full moon night sky",
        "text": "What the voice says in this scene"
      }
    ]
  }
]
```

---

## টিপস

- **শুধু Shorts চাইলে (এখনকার চ্যানেলের জন্য):** প্রম্পটে লেখো
  "Each video is a YouTube Short: 30–50 seconds (about 90–130 words), 4–6 scenes, and add `"format": "short"`"।
  তখন শুধু খাড়া (9:16) Short বানাবে আর আপলোড করবে, লম্বা ভিডিও না।
- **লম্বা ভিডিওর সাথে Short-ও চাইলে:** `config.yaml`-এ `shorts: enabled: true` থাকলে প্রতিটা লম্বা ভিডিওর একটা Short ভার্সনও যাবে।
- **British ভয়েস চাইলে:** `config.yaml`-এ `voice: "en-GB-RyanNeural"` দাও, আর প্রম্পটে
  "Use British spelling" লিখে দাও।
- ফাইল রাখার পর GitHub-এর **Actions → Check scripts** সবুজ টিক দেখালে ফাইল ঠিক আছে।
  লাল দেখালে ভেতরে কোন ফাইলে কী ভুল, লেখা থাকবে; সেটা Claude-কে দেখিয়ে ঠিক করিয়ে নাও।
