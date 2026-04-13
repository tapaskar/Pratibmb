# Launch Day Plan — April 13 (Today) + April 14 (Launch Day)

---

## TODAY — Sunday April 13 — Prep Day

Everything below must be done before you go to sleep tonight.

---

### 9:00 AM — GitHub Repo Polish (1 hour)

- [ ] **Add README badges** at the top:
  ```md
  ![Version](https://img.shields.io/github/v/release/tapaskar/Pratibmb)
  ![License](https://img.shields.io/badge/license-AGPL--3.0-blue)
  ![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Windows%20%7C%20Linux-lightgrey)
  ![Privacy](https://img.shields.io/badge/privacy-100%25%20local-green)
  ```
- [ ] **Add screenshots to README** — add a "Screenshots" section after "How it works" using images from `docs/screenshots/`:
  ```md
  ## Screenshots
  <p align="center">
  <img src="docs/screenshots/10_chat_conversation.png" width="600" alt="Chat with past-you">
  </p>
  ```
- [ ] **Set GitHub repo metadata** (Settings tab):
  - Description: "Chat with your 10-years-younger self. 100% local AI — no cloud, no telemetry."
  - Website: https://pratibmb.com
  - Topics: `ai`, `privacy`, `local-llm`, `whatsapp`, `rag`, `lora`, `fine-tuning`, `tauri`, `open-source`, `nostalgia`
- [ ] **Pin the repo** on your GitHub profile

### 10:00 AM — Missing Governance Files (30 min)

- [ ] **Create `CHANGELOG.md`** — document versions 0.1.0 through 0.5.0
- [ ] **Create `CODE_OF_CONDUCT.md`** — use Contributor Covenant 2.1
- [ ] **Create `.github/ISSUE_TEMPLATE/bug_report.md`**
- [ ] **Create `.github/ISSUE_TEMPLATE/feature_request.md`**
- [ ] **Create `.github/PULL_REQUEST_TEMPLATE.md`**
- [ ] Commit and push all

### 10:30 AM — Build & Release v0.5.0 (1-2 hours)

- [ ] **Push to GitHub** — `git push origin main`
- [ ] **Tag the release**: `git tag -a v0.5.0 -m "v0.5.0"` then `git push origin v0.5.0`
- [ ] **Wait for CI** — `build-desktop.yml` runs (~20-30 min)
- [ ] **Verify all 6 artifacts** are on the GitHub Releases page:
  - `Pratibmb_0.5.0_aarch64.dmg` (macOS ARM)
  - `Pratibmb_0.5.0_x64.dmg` (macOS Intel)
  - `Pratibmb_0.5.0_amd64.deb` (Linux)
  - `Pratibmb_0.5.0_amd64.AppImage` (Linux)
  - `Pratibmb_0.5.0_x64-setup.exe` (Windows)
  - `Pratibmb_0.5.0_x64_en-US.msi` (Windows)
- [ ] **Edit the release** — write release notes (pull from CHANGELOG.md), mark as "Latest release"
- [ ] **Verify `publish-packages.yml`** updates Homebrew/AUR/winget

### 12:30 PM — Test Every Download (1 hour)

- [ ] **Test macOS DMG** — download from releases, install, launch, import a WhatsApp chat, verify chat works
- [ ] **Test Windows installer** — if you have access to a Windows machine, or at minimum verify the .exe downloads and is not flagged by browsers
- [ ] **Test Linux .deb** — `sudo dpkg -i Pratibmb_*.deb && pratibmb doctor`
- [ ] **Test install scripts** — `curl -fsSL https://pratibmb.com/install.sh | bash` on a clean machine or Docker container
- [ ] **Test `pratibmb doctor`** — should report all green
- [ ] **Test first-launch model download** — verify both models (84MB embed + 2.3GB chat) download cleanly

### 1:30 PM — Website Final Check (30 min)

- [ ] **Check pratibmb.com loads** (HTTPS, correct version, all download links work)
- [ ] **Test OG image preview** — paste `https://pratibmb.com` into:
  - Twitter card validator: https://cards-dev.twitter.com/validator
  - Facebook debugger: https://developers.facebook.com/tools/debug/
  - LinkedIn inspector: https://www.linkedin.com/post-inspector/
  - Or just paste in a Slack/iMessage/WhatsApp/Telegram chat and verify the preview card looks good
- [ ] **Check mobile responsiveness** — open pratibmb.com on your phone
- [ ] **Deploy latest site** — push triggers `deploy-site.yml`

### 2:00 PM — Prepare All Accounts (30 min)

- [ ] **Hacker News** — log in, make sure your account is in good standing (do NOT create a new account — old accounts rank better)
- [ ] **Reddit** — log into accounts that will post on r/LocalLLaMA, r/selfhosted, r/privacy, r/opensource
  - If accounts are new (<30 days or low karma), do NOT post — it'll get spam-filtered
  - Comment on a few posts today to warm up the accounts
- [ ] **Twitter/X** — draft the thread in a thread tool (Typefully, or just Twitter's draft)
- [ ] **LinkedIn** — draft the post
- [ ] **Product Hunt** — log in, check maker settings, schedule for Day 2
- [ ] **Dev.to** — create account if needed, save blog post as draft
- [ ] **Instagram** — AirDrop carousel slides to phone, save as draft post

### 2:30 PM — Record Demo Video (1 hour)

This is the single highest-ROI asset you don't have yet. Every platform rewards video.

- [ ] **Screen record** (60-90 seconds, use QuickTime or OBS):
  1. Open Pratibmb — show welcome screen (5 sec)
  2. Drag a WhatsApp `.txt` file into the import zone (5 sec)
  3. Show embedding progress (5 sec, can speed up)
  4. Type a question in the chat input (10 sec)
  5. Show the response appearing (10 sec — hold so people can read)
  6. Scroll the year slider to a different year (5 sec)
  7. Ask another question, get another response (10 sec)
  8. Quick flash of the privacy badges at the bottom: "100% local · no cloud · no telemetry" (3 sec)
- [ ] **Export as MP4** (1080x1080 square for Instagram/Twitter, 1080x1920 for Reels/Stories)
- [ ] **Add captions/text overlay** in CapCut or iMovie if desired
- [ ] **Upload to YouTube as unlisted** — for embedding in the blog post and Product Hunt
- [ ] **Create a GIF** (10-15 sec loop of the chat exchange) for the README and Twitter

### 3:30 PM — Pre-Write All HN Comments (1 hour)

HN success depends on author engagement. Pre-write answers to likely questions so you can respond within minutes:

- [ ] Write your **first comment** (the technical deep-dive) — already in `hacker-news.md`
- [ ] Pre-write answers to:
  - "Is this therapy?" → See `hacker-news.md`
  - "What about hallucinations?" → See `hacker-news.md`
  - "Why not just use ChatGPT?" → See `hacker-news.md`
  - "Why Gemma-3-4B?" → See `hacker-news.md`
  - "Will this work on my 8GB MacBook Air?" → Yes, 8GB RAM is sufficient. The model needs ~3GB in memory.
  - "Can I use my own model?" → Not yet, but the architecture supports swapping models. PR welcome.
  - "What about languages other than English?" → Works for any language your messages are in. Gemma-3 is multilingual.
  - "I don't have 10 years of messages" → Even 1 year works. More data = more accurate voice, but it's useful from ~500 messages.
  - "This is creepy" → Valid feeling. It can be emotional. That's why there's a safety note in the app and README.
  - "Any plans for mobile?" → Not yet. The models need ~3GB RAM + decent CPU. Desktop-first for now.

### 4:30 PM — Final Personalization Pass (30 min)

- [ ] **Re-read every launch post** in `docs/launch/` with fresh eyes
- [ ] **Personalize** — replace generic examples with YOUR actual experience:
  - What year did you export?
  - What was the first question you asked?
  - What surprised you about the response?
  - What specific detail did the model get right that you'd forgotten?
- [ ] These personal details are what make posts feel authentic vs corporate

### 5:00 PM — Set Alarms & Prepare

- [ ] **Set alarm for 8:30 AM** tomorrow
- [ ] **Clear your calendar** for all of Monday — you need to be online ALL DAY responding to comments
- [ ] **Charge all devices**
- [ ] **Prepare a workspace** with laptop, phone, coffee — you'll be here for 12+ hours
- [ ] **Tell family/friends** you'll be unavailable Monday — launch day is a full-time job

---

## TOMORROW — Monday April 14 — Launch Day

Your #1 job tomorrow: **respond to every single comment within 15 minutes.** Nothing else matters as much. HN's ranking algorithm heavily rewards author engagement.

---

### 8:45 AM ET — Final Checks

- [ ] Open pratibmb.com — verify it's live
- [ ] Open GitHub releases — verify all assets are there
- [ ] Open all your pre-written responses in a doc for quick copy-paste
- [ ] Have HN, Reddit, Twitter open in separate tabs

### 9:00 AM ET — Submit to Hacker News

- [ ] Go to https://news.ycombinator.com/submit
- [ ] Title: `Show HN: Pratibmb – Chat with your past self using your real messaging history (100% local)`
- [ ] URL: `https://pratibmb.com`
- [ ] Submit
- [ ] **IMMEDIATELY** (within 60 seconds) post your first comment from `hacker-news.md`
- [ ] Save the HN link — you'll need it for cross-posting

### 9:00 - 11:00 AM — HN Watch (CRITICAL WINDOW)

- [ ] **Refresh HN every 5 minutes**
- [ ] **Reply to every comment within 10-15 minutes** — this is the single biggest factor for reaching the front page
- [ ] Be **technical, honest, specific** — HN values substance
- [ ] **Don't be defensive** — thank critics, acknowledge limitations honestly
- [ ] Don't ask anyone to upvote — instant ban
- [ ] If you hit the front page, the traffic spike will be enormous — verify the site stays up

### 9:30 AM ET — Post Twitter/X Thread

- [ ] Post the thread from `docs/launch/twitter-thread.md`
- [ ] Attach the demo video/GIF to tweet 1
- [ ] Add the HN link in the final tweet: "Live on HN: [link]"

### 10:00 AM ET — Post Instagram Carousel

- [ ] Post slides 1-5 from `docs/launch/instagram/`
- [ ] Paste the caption from `docs/launch/social-media-posts.md`
- [ ] Add `pratibmb.com` to your Instagram bio link

### 10:30 AM ET — Post to r/LocalLLaMA

- [ ] Use the post from `docs/launch/reddit-posts.md`
- [ ] This is your **highest-value Reddit audience** — they understand the tech
- [ ] Respond to every comment

### 11:00 AM ET — Post to WhatsApp

- [ ] Send to your close friends / tech group chats using the forward message from `docs/launch/social-media-posts.md`
- [ ] Post a WhatsApp Status using the text status version
- [ ] Ask friends to try it and share their reactions

### 12:00 PM ET — Post to r/selfhosted

- [ ] Use the r/selfhosted version from `docs/launch/reddit-posts.md`
- [ ] Emphasize the "runs entirely on your machine" angle

### 1:00 PM ET — Post LinkedIn

- [ ] Post from `docs/launch/linkedin-post.md`
- [ ] Tag relevant connections who might reshare
- [ ] This will reach your professional network

### 2:00 PM ET — Post to r/privacy

- [ ] Use the r/privacy version from `docs/launch/reddit-posts.md`
- [ ] Lead with the privacy architecture, not the AI features
- [ ] r/privacy can be skeptical — be transparent, link to source code

### 2:30 PM ET — Post Facebook

- [ ] Post from `docs/launch/social-media-posts.md` (Facebook Post 1)
- [ ] Personal story format works best on Facebook
- [ ] Share to any relevant groups you're in

### 3:00 PM ET — Post to r/opensource (optional)

- [ ] Only if you have karma in this sub
- [ ] Use the r/opensource version from `docs/launch/reddit-posts.md`

### ALL DAY — Monitor & Respond

- [ ] **HN comments** — reply within 15 min, every single one
- [ ] **Reddit comments** — reply within 30 min
- [ ] **Twitter replies** — reply within 30 min
- [ ] **GitHub issues** — someone WILL file a bug. Fix it fast. "Fixed in 30 minutes" is legendary on HN.
- [ ] **Monitor server/site** — if pratibmb.com goes down, fix immediately
- [ ] Keep a notepad of feedback themes — you'll use these for the follow-up post

### 6:00 PM ET — Evening Check-in

- [ ] Post an Instagram Story with real-time stats: "X downloads in the first 8 hours"
- [ ] Reply to any remaining comments
- [ ] Screenshot any notable reactions for social proof

### 9:00 PM ET — Day 1 Wrap

- [ ] Final reply sweep across all platforms
- [ ] Note your HN rank, GitHub stars, downloads for the follow-up
- [ ] Get sleep — Day 2 matters too

---

## DAY 2 — Tuesday April 15

### Morning

- [ ] **Reply to all overnight comments** (Europeans, Asians will have commented)
- [ ] **Launch on Product Hunt** — use `docs/launch/product-hunt.md`
  - Schedule for 12:01 AM PT (Product Hunt resets at midnight Pacific)
  - Or submit manually in the morning
- [ ] **Cross-post blog to Dev.to** — use `docs/launch/blog-post.md`
  - Add canonical URL pointing to your blog if you have one
- [ ] **Cross-post to Medium** (Towards Data Science or Level Up Coding)

### Afternoon

- [ ] Post the **Instagram Reel** if you recorded a demo video
- [ ] **Boost the Instagram carousel** as an ad if it got good engagement
- [ ] Continue responding to all comments across platforms
- [ ] Fix any bugs filed on GitHub — speed matters for first impressions

---

## DAY 3-7 — Momentum

- [ ] **Share user reactions/screenshots** on Twitter and Instagram Stories
- [ ] **Update README** with social proof: "Featured on Hacker News", GitHub star count
- [ ] **Add "As seen on" badges** to pratibmb.com if applicable
- [ ] **Write a follow-up tweet**: "X people downloaded Pratibmb in 72 hours. Here's what I learned."
- [ ] **Fix bugs fast** — every quick fix builds trust
- [ ] **Engage with anyone who tweets about it** — retweet, thank them, answer questions
- [ ] **Submit to newsletters**: Hacker Newsletter, TLDR, Console.dev, Ben's Bites, Changelog

---

## CRITICAL RULES

| Rule | Why |
|------|-----|
| **Reply to every comment** | #1 factor for HN front page and Reddit traction |
| **Be online all day** | First 6 hours determine everything |
| **Be honest about limitations** | "It can hallucinate" builds more trust than "it's perfect" |
| **Never ask for upvotes** | Instant ban on HN, looks desperate everywhere |
| **Link to pratibmb.com, not GitHub** | Landing page converts 5x better than a repo page |
| **Fix bugs in public** | "Fixed in [commit link]" posted as a reply is the best marketing |
| **Don't spam** | Space Reddit posts 2-3 hours apart. One post per sub. |
| **Personal > corporate** | "I asked it..." beats "Users can..." |

---

## WHAT YOU SHOULD HAVE READY (checklist)

| Asset | Status | Location |
|-------|--------|----------|
| HN post + first comment | Ready | `docs/launch/hacker-news.md` |
| Twitter thread | Ready | `docs/launch/twitter-thread.md` |
| Reddit posts (4 subs) | Ready | `docs/launch/reddit-posts.md` |
| LinkedIn post | Ready | `docs/launch/linkedin-post.md` |
| Product Hunt listing | Ready | `docs/launch/product-hunt.md` |
| Blog post (Dev.to/Medium) | Ready | `docs/launch/blog-post.md` |
| Instagram carousel (5 slides) | Ready | `docs/launch/instagram/01-05_*.png` |
| Instagram ad (standalone) | Ready | `docs/launch/instagram/06_standalone_ad.png` |
| Facebook posts | Ready | `docs/launch/social-media-posts.md` |
| WhatsApp messages | Ready | `docs/launch/social-media-posts.md` |
| Instagram/FB caption | Ready | `docs/launch/social-media-posts.md` |
| Demo video (60-90 sec) | **NOT YET** | Record today |
| Demo GIF (10-15 sec) | **NOT YET** | Extract from video today |
| GitHub release v0.5.0 | **NOT YET** | Tag + build today |
| OG image tested | **NOT YET** | Test today |
| Pre-written HN answers | **NOT YET** | Write today |
| All accounts logged in | **NOT YET** | Verify today |
