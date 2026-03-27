chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === "extract") {
    try {
      const allLinks = [...document.querySelectorAll("a[href]")]
        .map((a) => {
          try {
            return a.href;
          } catch {
            return null;
          }
        })
        .filter((h) => h && h.startsWith("http"))
        .slice(0, 30000);
      const getMeta = (selectors) => {
        for (const sel of selectors) {
          const el = document.querySelector(sel);
          if (el) {
            const val = el.getAttribute("content") || el.textContent || "";
            if (val.trim()) return val.trim();
          }
        }
        return "";
      };

      const data = {
        url: location.href,
        hostname: location.hostname,
        title: document.title || "",
        text: (document.body.innerText || "").slice(0, 15000),
        links: allLinks,
        meta: {
          description: getMeta([
            'meta[name="description"]',
            'meta[property="og:description"]',
          ]),
          author: getMeta([
            'meta[name="author"]',
            'meta[property="article:author"]',
            '[rel="author"]',
          ]),
          ogType: getMeta(['meta[property="og:type"]']),
          publishedTime: getMeta([
            'meta[property="article:published_time"]',
            'meta[name="date"]',
            "time[datetime]",
          ]),
          siteName: getMeta(['meta[property="og:site_name"]']),
          lang:
            document.documentElement.lang ||
            getMeta(['meta[http-equiv="content-language"]']) ||
            "",
        },
      };

      sendResponse({ success: true, data });
    } catch (err) {
      sendResponse({ success: false, error: err.message });
    }
  }
  return true;
});