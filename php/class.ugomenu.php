<?php

/*
UGO builder class for Sudomemo
github.com/Sudomemo | www.sudomemo.net

Written by James Daniel
github.com/jaames | rakujira.jp

Format documentation can be found on the Flipnote-Collective wiki:
https://github.com/Flipnote-Collective/flipnote-studio-docs/wiki/.ugo-menu-format
*/

class ugomenu {
  var $types = [
    "0" =>          "0",
    "1" =>          "1",
    "2" =>          "2",
    "3" =>          "3",
    "4" =>          "4",
    "index" =>      "0",
    "small_list" => "1",
    "grid" =>       "2",
    "list" =>       "4",
  ];

  var $meta = [];
  var $menu = [];
  var $embeds = [];

  function writeLabel($text) {
    return base64_encode(mb_convert_encoding($text, "UTF-16LE"));
  }

  function setType($value) {
    $this->meta["type"] = $this->types[$value];
  }

  // set uppertitle, upperlink, uppersubbottom, etc
  function setMeta($value, $text) {
    $this->meta[strtolower($value)] = $text;
  }

  // add a dropdown item, e.g. recent, most popular, featured, etc
  function addDropdown($args) {
    if (!isset($this->menu["dropdown"])) {
      $this->menu["dropdown"] = [];
    }
    array_push($this->menu["dropdown"], [
      "url"      => isset($args["url"])      ? $args["url"]      : "",
      "label"    => isset($args["label"])    ? $args["label"]    : "",
      "selected" => isset($args["selected"]) ? $args["selected"] : "0",
    ]);
  }

  // add a corner button, e.g. 'post flipnote', 'add comment', etc
  function addButton($args) {
    if (!isset($this->menu["button"])) {
      $this->menu["button"] = [];
    }
    array_push($this->menu["button"], [
      "url"   => isset($args["url"])   ? $args["url"]   : "",
      "label" => isset($args["label"]) ? $args["label"] : "",
    ]);
  }

  // menu item, depending on the layout type, this might be a letter, a thumbnail, or a link button
  function addItem($args) {
    if (!isset($this->menu["item"])) {
      $this->menu["item"] = [];
    }
    if (isset($args["file"])){
      $this->addFile($args["file"]);
      $args["icon"] = count($this->embeds) - 1;
    }
    array_push($this->menu["item"], [
      "url"     => isset($args["url"])     ? $args["url"]     : "",
      "label"   => isset($args["label"])   ? $args["label"]   : "",
      "icon"    => isset($args["icon"])    ? $args["icon"]    : "104",
      "counter" => isset($args["counter"]) ? $args["counter"] : "",
      "lock"    => isset($args["lock"])    ? $args["lock"]    : "",
      "unknown" => isset($args["unknown"]) ? $args["unknown"] : "0",
    ]);
  }

  // embedded file
  function addFile($path) {
    array_push($this->embeds, [
      "ext"  => pathinfo($path, PATHINFO_EXTENSION),
      "path" => $path
    ]);
  }

  function getUGO(){

    $ret = "";

    $sectionTable = [];
    $menuData = [];

    // TYPE 0 -- LAYOUT TYPE
    array_push($menuData, join("\t", [
      "0",
      isset($this->meta["type"]) ? $this->meta["type"] : "4"
    ]));

    // TYPE 1 -- TOP SCREEN LAYOUT
    if( isset($this->meta["upperlink"]) ) {
      array_push($menuData, join("\t", [
        "1",
        "1",
        $this->meta["upperlink"]
      ]));
    }
    else {
      array_push($menuData, join("\t", [
        "1",
        "0",
        isset($this->meta["uppertitle"])     ? $this->writeLabel($this->meta["uppertitle"])     : "",
        isset($this->meta["uppersubleft"])   ? $this->writeLabel($this->meta["uppersubleft"])   : "",
        isset($this->meta["uppersubright"])  ? $this->writeLabel($this->meta["uppersubright"])  : "",
        isset($this->meta["uppersubtop"])    ? $this->writeLabel($this->meta["uppersubtop"])    : "",
        isset($this->meta["uppersubbottom"]) ? $this->writeLabel($this->meta["uppersubbottom"]) : "",
      ]));
    }

    // TYPE 2 -- DROPDOWN ITEMS
    if( isset($this->menu["dropdown"]) ) {
      foreach ($this->menu["dropdown"] as $item) {
        array_push($menuData, join("\t", [
          "2",
          $item["url"],
          $this->writeLabel($item["label"]),
          $item["selected"]
        ]));
      }
    }

    // TYPE 3 -- BUTTONS
    if( isset($this->menu["button"]) ) {
      foreach ($this->menu["button"] as $item) {
        array_push($menuData, join("\t", [
          "3",
          $item["url"],
          $this->writeLabel($item["label"])
        ]));
      }
    }

    // TYPE 4 -- ITEMS
    if( isset($this->menu["item"]) ) {
      foreach ($this->menu["item"] as $item) {
        array_push($menuData, join("\t", [
          "4",
          $item["url"],
          $item["icon"],
          $this->writeLabel($item["label"]),
          $item["counter"],
          $item["lock"],
          $item["unknown"],
        ]));
      }
    }

    // join all the items using newlines
    $menuData = join("\n", $menuData);

    // HEADER

    // get the byte length of this section and add it to the section table
    $menuDataLen = mb_strlen($menuData, 'UTF-8');
    array_push($sectionTable, $menuDataLen);

    // pad the actual length to the nearest multiple of four
    $menuData = str_pad($menuData, ceil($menuDataLen/4) * 4, "\0");

    // calculate the embed section length
    $embedLen = false;
    if (sizeof($this->embeds) > 0){
      $embedLen = 0;
      foreach ($this->embeds as $item) {
        // .ppm is 1696 bytes while ntft is 2024
        $embedLen += $item["ext"] === 'ppm' ? 1696 : 2048 ;
      }
      // add this length to the section table
      array_push($sectionTable, $embedLen);
    }

    // write the magic ('UGAR') and number of sections
    $ret .= pack("a4V", "UGAR", count($sectionTable));
    // write the length of each section
    foreach ($sectionTable as $length) {
      $ret .= pack("V", $length);
    }

    // append the menu data
    $ret .= $menuData;

    // EMBEDS

    if ($embedLen !== false) {
      foreach ($this->embeds as $item) {
        // check that the file exists
        if(!file_exists($item["path"])){
          $filename = $item["path"];
          error_log("Error generating Ugomenu: could not open file $filename");
          exit();
        }
        // open the file
        $file = fopen($item["path"], 'r');
        if ($item["ext"] === 'ppm') {
          $ret .= fread($file, 1696);
        }
        elseif ($item["ext"] === 'ntft') {
          $ret .= fread($file, 2048);
        }
        fclose($file);
      }
    }

    return $ret;
  }
}
