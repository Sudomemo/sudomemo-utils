# sudomemo-utils
A collection of misc. scripts for reading/writing Flipnote Studio DSi's proprietary formats. Created for Sudomemo.

## Contents

#### PHP Classes

* **[class.ugomenu.php](#classugomenuphp)** - builds [`.ugo` menus](https://github.com/Flipnote-Collective/flipnote-studio-docs/wiki/.ugo-menu-format) on-the-fly.
* **[class.ppmParser.php](#classppmparserphp)** - parses metadata from Flipnote and Comment `.ppm` files.

#### Python Scripts

* **ugoImage.py** - converts to and from the [`.nbf`](https://github.com/Flipnote-Collective/flipnote-studio-docs/wiki/.nbf-image-format), [`.npf`](https://github.com/Flipnote-Collective/flipnote-studio-docs/wiki/.npf-image-format) and [`.ntft`](https://github.com/Flipnote-Collective/flipnote-studio-docs/wiki/.ntft-image-format) image formats.
* **ugoImageViewer.py** - experimental native viewer for the image formats handled by ugoImage.py

## class.ugomenu.php

### Getting Started

```php
<?php

// import the ugomenu class:

require("path/to/class.ugomenu.php");

// start a new ugomenu, for these examples, we'll create a generic "demo" menu:

$demoMenu = new ugomenu;
```

### Methods

#### setType

**Use:**

Set the menu type, from one of the values documented [here](https://github.com/Flipnote-Collective/flipnote-studio-docs/wiki/.ugo-menu-format#type-0---menu-type-indicator).

**Example:**

```php
// set the menu type to type 0 (the same as the 'index' menu)

$demoMenu->setType("0");
```

#### setMeta

**Use:**

Set top screen text / background image by setting the equivalent meta-tag value, documented [here](https://github.com/Flipnote-Collective/flipnote-studio-docs/wiki/HTML#top-screen).

**Example:**

```php
// set the top screen title to "demo page":

$demoMenu->setMeta("uppertitle", "demo page");

// set the top screen subtitle to "demo in progress":

$demoMenu->setMeta("uppersubbottom", "demo in progress");
```

#### addDropdown

**Use:**

Add a dropdown option to the menu, like the "Recent Flipnotes" / "Most Popular" options on the "All Flipnotes" menu.

**Example:**

```php
// create a dropdown option with the label "select me!"
// when the user selects this option they will be navigated to www.example.com/path/to/page.htm

$demoMenu->addDropdown([
  "label" => "select me!",
  "url"   => "http://www.example.com/path/to/page.htm"
]);

// to set an item as the preselected option:

$demoMenu->addDropdown([
  "label"    => "select me!",
  "url"      => "http://www.example.com/path/to/page.htm",
  "selected" => "1"
]);
```

#### addButton

**Use:**

Add a button in the bottom-right corner of the screen, like the "Post Here" button on a channel menu.

Up to two of these can be used on the same menu.

**Example:**

```php
// create a button with the label "tap me!":
// when the user taps this button, they will be navigated to www.example.com/path/to/page.htm

$demoMenu->addButton([
  "label" => "tap me!",
  "url"   => "http://www.example.com/path/to/page.htm"
]);
```

#### addItem

**Use:**

Add a menu item, or a thumbnail if using the grid layout type.

Built-in icon values are documented [here](https://github.com/Flipnote-Collective/flipnote-studio-docs/wiki/.ugo-menu-format#icons).

**Example:**

```php
// create a menu item with the label "tap me!":
// when the user taps this item, they will be navigated to www.example.com/path/to/page.htm

$demoMenu->addItem([
  "label" => "tap me!",
  "url"   => "http://www.example.com/path/to/page.htm",
  // use an internal icon value:
  "icon"  => "104"
]);

// create a menu item with a custom icon:

$demoMenu->addItem([
  "label" => "tap me!",
  "url"   => "http://www.example.com/path/to/page.htm",
  // embed a custom ntft image and use it as the icon for this image:
  "file"  => "/local/path/to/icon.ntft"
]);

// or for a flipnote grid thumbnail:

$demoMenu->addItem([
  "url"  => "http://www.example.com/path/to/page.htm",
  "file" => "/local/path/to/flipnote.ppm"
]);

// you can also add a lock icon or counter to the item:
// on Flipnote grid menus, the counter is used for the star count

$demoMenu->addItem([
  "label" => "tap me!",
  "url"   => "http://www.example.com/path/to/page.htm",
  "icon"  => "104",
  // add a lock:
  "lock"  => "1",
  // add a counter:
  "counter" => "9999"
]);
```

#### getUGO

**Use:**

Build the ugomenu and return the data as a string, ready to send to the DSi client.

**Example:**

```php
echo $demoMenu->getUGO();
```

## class.ppmParser.php

### Getting Started

```php
<?php

// import the ppmParser class:

require("path/to/class.ppmParser.php");

// start a new parser instance:

$ppm = new ppmParser;

// open a PPM file for parsing:

$ppm->open("path/to/flipnote.ppm");
```

### Methods

#### isCorrupted

**Use:**

Does a simple "completeness" check on the PPM to check that all the data necessary is present in the file, acting as a safeguard against "corrupted" Flipnotes that got cut off on upload.

Returns 1 if the PPM is corrupted, else 0.

#### getMeta

**Use:**

Parses and returns the metadata for the open PPM file.
