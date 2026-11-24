# ready-fabelo/ → Fabelo Studio channel (always Private)

Put a finished video here with a JSON file of the same name and push. The
"Upload Fabelo Studio video" workflow uploads it as **Private** to Fabelo Studio
using only the `FABELO_YT_REFRESH_TOKEN` secret, then writes the link back.

```json
{
  "video": "my-film.mp4",
  "title": "Don't Throw Away Your Mistakes | Animated Short Film",
  "description": "...",
  "tags": ["animated short film", "motivation"],
  "category_id": "1",
  "thumbnail": "my-film.jpg"
}
```

`category_id`: 1 = Film & Animation (emotional shorts), 27 = Education (explainers).
A JSON that already has `"url"` is skipped, so nothing is uploaded twice.
