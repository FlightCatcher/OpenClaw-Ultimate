(function () {
  "use strict";

  var replacements = [
    [/OpenClaw Control UI/g, "VELA Control UI"],
    [/OpenClaw Control/g, "VELA Control"],
    [/Gateway Dashboard/g, "Local Agent Dashboard"],
    [/\bOpenClaw\b/g, "VELA"],
  ];
  var observedRoots = new WeakSet();

  function replaceText(value) {
    var result = value;
    for (var i = 0; i < replacements.length; i += 1) {
      result = result.replace(replacements[i][0], replacements[i][1]);
    }
    return result;
  }

  function brandElement(element) {
    var attributes = ["alt", "aria-label", "placeholder", "title"];
    for (var i = 0; i < attributes.length; i += 1) {
      var name = attributes[i];
      if (!element.hasAttribute || !element.hasAttribute(name)) continue;
      var current = element.getAttribute(name);
      var branded = replaceText(current || "");
      if (branded !== current) element.setAttribute(name, branded);
    }
  }

  function brandTree(root) {
    if (!root) return;
    if (root.nodeType === Node.TEXT_NODE) {
      var current = root.nodeValue || "";
      var branded = replaceText(current);
      if (branded !== current) root.nodeValue = branded;
      return;
    }
    if (root.nodeType === Node.ELEMENT_NODE) {
      var tag = root.tagName;
      if (tag === "SCRIPT" || tag === "STYLE" || tag === "CODE" || tag === "PRE") return;
      brandElement(root);
      if (root.shadowRoot) observeRoot(root.shadowRoot);
    }

    var walker = document.createTreeWalker(
      root,
      NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT,
    );
    var node;
    while ((node = walker.nextNode())) {
      if (node.nodeType === Node.TEXT_NODE) {
        var parentTag = node.parentElement && node.parentElement.tagName;
        if (
          parentTag === "SCRIPT" ||
          parentTag === "STYLE" ||
          parentTag === "CODE" ||
          parentTag === "PRE"
        ) {
          continue;
        }
        var text = node.nodeValue || "";
        var replacement = replaceText(text);
        if (replacement !== text) node.nodeValue = replacement;
      } else {
        brandElement(node);
        if (node.shadowRoot) observeRoot(node.shadowRoot);
      }
    }
  }

  function observeRoot(root) {
    if (!root || observedRoots.has(root)) return;
    observedRoots.add(root);
    brandTree(root);
    new MutationObserver(function (mutations) {
      for (var i = 0; i < mutations.length; i += 1) {
        var mutation = mutations[i];
        if (mutation.type === "characterData") {
          brandTree(mutation.target);
          continue;
        }
        for (var j = 0; j < mutation.addedNodes.length; j += 1) {
          brandTree(mutation.addedNodes[j]);
        }
      }
    }).observe(root, { childList: true, characterData: true, subtree: true });
  }

  var originalAttachShadow = Element.prototype.attachShadow;
  Element.prototype.attachShadow = function (init) {
    var shadowRoot = originalAttachShadow.call(this, init);
    observeRoot(shadowRoot);
    return shadowRoot;
  };

  document.title = "VELA · Local Agent";
  observeRoot(document.documentElement);
  window.addEventListener("DOMContentLoaded", function () {
    document.title = "VELA · Local Agent";
    brandTree(document.documentElement);
  });
})();
