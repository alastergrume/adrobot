"use strict";

// Links from the application look like /admin/#!/campaigns/93212 (as in the real Keitaro admin).
const match = location.hash.match(/campaigns\/(\d+)/);
const card = match && document.getElementById("campaign-" + match[1]);
if (card) { card.classList.add("highlight"); card.scrollIntoView(); }
