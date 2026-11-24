#!/usr/bin/env bash
# Downloads free, reusable assets into assets/ (run by the "Fetch assets" workflow).
#  - World map: NASA Blue Marble (public domain, NASA Visible Earth)
#  - Music: Kevin MacLeod, incompetech.com (CC BY 4.0, credit added to the video description)
set -u
cd "$(dirname "$0")/.."
mkdir -p assets/map assets/music

get() {  # get <url> <file>
  if [ -s "$2" ]; then echo "have $2"; return 0; fi
  if curl -fsSL --retry 3 --max-time 180 -o "$2.part" "$1"; then mv "$2.part" "$2"; echo "got $2 ($(du -h "$2" | cut -f1))"
  else rm -f "$2.part"; echo "FAILED $1"; fi
}

get "https://eoimages.gsfc.nasa.gov/images/imagerecords/73000/73909/world.topo.bathy.200412.3x5400x2700.jpg" assets/map/blue-marble.jpg
get "https://eoimages.gsfc.nasa.gov/images/imagerecords/144000/144898/BlackMarble_2016_3km.jpg" assets/map/black-marble.jpg

credits=assets/music/CREDITS.txt
for t in "Investigations" "Wallpaper" "Fluffing a Duck" "Sneaky Snitch" "Pixel Peeker Polka - faster" "Carefree" "Monkeys Spinning Monkeys" "Life of Riley"; do
  f="assets/music/$(echo "$t" | tr 'A-Z ' 'a-z-' | tr -cd 'a-z0-9-').mp3"
  url="https://incompetech.com/music/royalty-free/mp3-royaltyfree/$(echo "$t" | sed 's/ /%20/g').mp3"
  get "$url" "$f"
  if [ -s "$f" ] && ! grep -q "^$(basename "$f")|" "$credits" 2>/dev/null; then
    echo "$(basename "$f")|\"$t\" Kevin MacLeod (incompetech.com). Licensed under Creative Commons: By Attribution 4.0 License http://creativecommons.org/licenses/by/4.0/" >> "$credits"
  fi
done
ls -la assets/map assets/music
