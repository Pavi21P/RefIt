# Third-party notices

## Design guidance

RefIt's design process used unslop by Damir Sokolovsky:
https://github.com/heydamir/unslop

The guidance is licensed under Creative Commons Attribution 4.0:
https://creativecommons.org/licenses/by/4.0/

The interface is an original implementation based on the user's supplied layout references. No unslop source files are bundled. Design choices adapted from the guidance are described in docs/design.md. No endorsement is implied.

## Sample artworks

Images in static/studies are public-domain images supplied by the Art Institute of Chicago under its CC0 open-access designation. Metadata, source links, and original image URLs are in gallery/sample_art.json. The API confirmed the public-domain status of each included work when downloaded.

https://creativecommons.org/publicdomain/zero/1.0/
https://www.artic.edu/open-access

Thumbnails have been resized by the museum's image service. Artwork titles and artists remain attributed in the sample gallery. These images retain their public-domain status independently of the software license.

## Dependencies

Python dependencies retain their own licenses. See the installed package distributions for Django, django-axes, Pillow, WhiteNoise, Waitress, asgiref, sqlparse, and tzdata. Development tooling (Playwright and Ruff) is not distributed with the application.
