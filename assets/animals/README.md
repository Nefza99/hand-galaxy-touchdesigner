# Animal / Insect Image Assets

This folder now includes a bundled starter pack with one generated PNG per
animal/insect keyword, so the speech-to-image effect works out of the box.
You can replace any file with your own art later using the same filename.

Drop your images here, one file per keyword. Naming rules:

- Filename must match the keyword exactly (lowercase, no spaces needed — underscores also work)
- Supported formats: PNG, JPG, JPEG, WEBP, BMP, TIF
- Recommended size: 320×320 px minimum, square or close to square
- PNG with transparency strongly recommended so the glow highlight looks clean

## Examples

```
cat.png
dog.jpg
butterfly.png
bee.png
dragonfly.png
spider.jpg
```

## What happens if an image is missing?

A labelled placeholder is shown automatically. The app will not crash.
The placeholder shows a "?" icon and the keyword name.

## Where to get images

- Unsplash (https://unsplash.com) — free, no attribution required
- Pixabay (https://pixabay.com) — free, includes transparent PNGs
- Your own photos or illustrations
- Clip art / vector exports saved as PNG with transparency

## Regenerate the starter pack

```powershell
.\.venv\Scripts\python.exe scripts\generate_animal_asset_pack.py
```

## Full keyword list

The following words trigger image lookups. If no file exists for a word,
the placeholder is used.

Animals: cat, dog, horse, cow, pig, sheep, goat, rabbit, fox, wolf, bear,
deer, lion, tiger, leopard, cheetah, elephant, giraffe, zebra, hippo, rhino,
gorilla, monkey, orangutan, chimp, panda, koala, kangaroo, whale, dolphin,
seal, otter, beaver, squirrel, rat, mouse, hamster, bird, eagle, hawk, owl,
parrot, penguin, pelican, flamingo, ostrich, peacock, crow, raven, duck,
swan, sparrow, robin, hummingbird, snake, lizard, gecko, iguana, crocodile,
alligator, turtle, tortoise, frog, toad, salamander, newt, fish, shark,
salmon, tuna, goldfish, clownfish, octopus, squid, jellyfish, crab,
lobster, shrimp.

Insects: bee, wasp, hornet, ant, termite, butterfly, moth, caterpillar,
beetle, ladybug, ladybird, fly, mosquito, gnat, dragonfly, damselfly,
grasshopper, cricket, locust, spider, scorpion, mantis, cockroach,
firefly, tick, flea, louse, centipede, millipede.
