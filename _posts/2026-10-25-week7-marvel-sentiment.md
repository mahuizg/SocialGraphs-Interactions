---
title: "Allies, enemies and the sentence behind the link"
week: 7
summary: "Is the sentence behind a Marvel hyperlink positive or negative, and do negative links cross network communities?"
permalink: /week7-marvel-sentiment.html
plotly: true
scripts:
  - /assets/week7/story.js
---

# Allies, enemies and the sentence behind the link

*Week 7 Go Nuts · Marvel text + network*

<div class="hook" data-story-base="{{ '/assets/week7/' | relative_url }}">
<blockquote class="hook__quote"><p>“Despite the combined attacks of the God Squad, Ares is unscathed and engages Hercules in direct combat as Zeus and Hera battle Galactus and the other members of the Squad.”</p><cite class="hook__cite">Ares’s Wikipedia page, on Hercules</cite></blockquote>
<p class="hook__punch">A sentiment model, DistilBERT, scores this sentence <span class="hook__score">+1.00</span>, as positive as a sentence can get. Elsewhere on the same page, “Ares has hated Hercules ever since Hercules killed Ares’ pets…” scores −0.96. Averaged over all 15 sentences, the link Ares → Hercules comes out at +0.09. We labeled it <em>enemy</em>.</p>
</div>

<p class="verdict"><strong>Short answer: no.</strong> Enemy links are only about 2 points more common <em>between</em> network communities than <em>within</em> them, and that difference is indistinguishable from chance. Along the way we found that the three sentiment instruments barely agree with each other.</p>

<ul class="stats">
<li class="stat"><span class="stat__value">1,539<small> / 1,784</small></span><span class="stat__label">hyperlinks traced back to a sentence (86.3%)</span></li>
<li class="stat"><span class="stat__value">5,320</span><span class="stat__label">sentences scored by three sentiment instruments</span></li>
<li class="stat"><span class="stat__value">0.93</span><span class="stat__label">best validation AUC (DistilBERT, on 40 hand-labeled links)</span></li>
<li class="stat stat--accent"><span class="stat__value">p = 0.18</span><span class="stat__label">for “enemy links cross communities”, against shuffled signs</span></li>
</ul>

## Can a sentence tell an ally from an enemy?

Every link in the Marvel network is a sentence somewhere: Ares's page links to Hercules because it says something about him. Our question: **do "enemy" links run between network communities more often than within them?** If communities are teams and factions, fights should cross their borders. To test it we first need to know which links are enemies, so we score the sentence where A mentions B and check whether that sentiment can tell allies from enemies at all.

## How do you find the sentence behind a link?

The page text has no link markup, so we found B's *names* on A's page. Each character got a small alias table (title, alter ego, plus 61 hand-picked names such as Spider-Man → Peter Parker). We kept only story sections; "In other media" was mostly cast lists. **1,539 of 1,784 links (86.3%)** got at least one sentence, 5,320 sentences in total.

Each sentence was then scored by three instruments, and the scores were averaged per link:

- **DistilBERT** (`distilbert-base-uncased-finetuned-sst-2-english`), a neural model trained on movie reviews
- **VADER**, a sentiment word list with rules
- **A small keyword list**: *enemy, foe, rival, nemesis, killed, fought* vs. *ally, teammate, friend, married, partner, love*

## Which instrument would you trust?

Before trusting any instrument with 1,784 links, we hand-labeled 40 random links (16 ally, 2 family, 8 enemy, 14 neutral). Now it's your turn: read the sentences, guess the relation, and see what we and the three instruments said.

<figure class="panel widget" id="game">
<figcaption><span class="fig-num">Figure 1</span>Ally or enemy? Our 40 hand-labeled links<span class="try">Try: guess before you reveal. Watch how often the three instruments disagree with each other, and with you.</span></figcaption>
<div class="widget__stage"><p class="widget__fallback">This game needs JavaScript.</p></div>
</figure>

Over all 40 links, this is how often each instrument's sign matched our label, and how well it ranks enemies below allies and family (AUC, 0.5 = chance):

| Instrument | Enemy → negative | Ally/family → positive | AUC [95% CI] |
|---|---|---|---|
| **DistilBERT** | 5/8 | 17/18 | **0.93** [0.80, 1.00] |
| VADER | 7/8 | 8/18 | 0.69 [0.44, 0.90] |
| Keywords | 3/8 | 4/18 | 0.76 [0.61, 0.90] |

DistilBERT wins, so it is the instrument we carry into the network.

## Do enemies cross community lines?

We ran Louvain (seed 42) on the undirected giant component and got 8 communities (Q = 0.386). Before testing anything, meet the network: pick a character and read the sentences behind its links.

<figure class="panel widget" id="explorer">
<figcaption><span class="fig-num">Figure 2</span>Every link of one character, colored by DistilBERT's sign<span class="try">Try: switch to Spider-Man or Wolverine, then click the red lines. Are those really enemies?</span></figcaption>
<div class="widget__stage"><p class="widget__fallback">This explorer needs JavaScript.</p></div>
</figure>

Then the test: we compared the share of negative links within and between communities. As the null model, we shuffled the signs across links 1,000 times, keeping the network fixed. If enemies really cross community lines, our real difference should land far out in the tail of the shuffled ones.

<figure class="panel widget" id="nullsim">
<figcaption><span class="fig-num">Figure 3</span>Our difference against 1,000 shuffled worlds<span class="try">Try: press run, and guess where the red line will land before the shuffles finish.</span></figcaption>
<div class="widget__stage"><div class="widget__fallback"><p>This animation needs JavaScript. Static version:</p><img src="{{ '/assets/week7/null_delta.png' | relative_url }}" alt="Null distribution of the between-minus-within difference in negative links, with the observed value marked"></div></div>
</figure>

Negative links make up **28.8%** of links within communities and **31.1%** between them, a difference of **Δ = +2.3 points**. Against 1,000 shuffles of the signs this gives **z = 0.99, one-sided empirical p = 0.18** (the share of the 1,000 shuffles with Δ at least as large as ours; z assumes a normal null and would give 0.16). The ticks under the histogram show Δ for 20 different Louvain seeds. It is positive every time (+0.1 to +5.1 points), but p ranges from 0.013 to 0.51 depending on the seed.

**Answer:** enemies are only slightly more common between communities than within them, and with this measurement we cannot tell the difference apart from chance.

## Why do the instruments disagree so much?

This was the biggest surprise. **The instruments barely agree.** The rank correlation between them is 0.05–0.26. On single sentences, DistilBERT and VADER have the same sign only 61% of the time.

<figure class="panel widget" id="disagree">
<figcaption><span class="fig-num">Figure 4</span>DistilBERT vs. VADER, all 5,320 sentences<span class="try">Try: hover over (or tap) the red dots in the shaded corners. Those are the sentences where the two instruments disagree.</span></figcaption>
<div class="widget__stage"><p class="widget__fallback">This plot needs JavaScript.</p></div>
</figure>

- **VADER reads action as hostility**, even when the two characters fight on the *same* side (DistilBERT +0.82, VADER −0.70):

  > "During the Fear Itself storyline, Anya, X-23, Amadeus Cho, Power Man, and Thunderstrike are teleported to a station in the middle of the Pacific Ocean where they fight samurai Shark Men."

- **DistilBERT is very sure about sentences that say nothing.** A 22-name tournament roster that includes Hyperion scores **+0.99**:

  > "For the tournament, the Phoenix chooses Doctor Doom, Man-Thing, Luke Cage, Moon Girl, Devil Dinosaur, Orb, Hyperion, Howard the Duck, Nighthawk, Shang-Chi, Wolverine, Valkyrie, Black Knight, American Eagle, Red Widow, Shanna the She-Devil, Zabu, Namor, She-Hulk, Captain America, Black Panther, and Echo."

  Our 14 neutral links got scores from −0.99 to +1.00.

## What does "negative" actually mean?

We read the most negative links on each side of the community border:

- A real enemy link that crosses communities, Ricochet → Wolverine (DistilBERT −1.00):

  > "Ricochet becomes disillusioned because his efforts had not earned him any fame or recognition, and blames himself for Hornet's death at the hands of a brainwashed Wolverine."

- Negative, but misfortune rather than hostility, Robbie Baldwin → Steel Spider (−1.00):

  > "During the team's mission to capture Steel Spider, Penance suffers a mental breakdown."

- Negative, but it's editorial history, Zombie → Jericho Drumm (−1.00):

  > "…Simon Garth was reanimated in the horror-comics magazine Bizarre Adventures #33 (Dec. 1982), in an out-of-chronology story hard to reconcile with the remainder of the character's continuity."

So "negative" mixes hostility, bad luck and comic-book publishing history.

## What can't this tell us?

**The instruments score the sentence, not the relation between A and B.** The tone of a sentence often comes from a third party (a shared villain), from misfortune, or from editorial history. Our validation also rests on only 8 hand-labeled enemy links. Our null result therefore means "not detectable with sentence sentiment", not "enemy links don't cross communities".
