# Daily Nihongo / Everyday Japanese — Content Roadmap

> *Goal: a channel that lasts forever.* At 4 videos/day, no word repeats for
> ~75 days *per level*. With JLPT N5→N1 + themed expansions, this is good for
> 10+ years of unique content.

## How leveling works

The picker (in `pipeline.py`) reads `words.txt` per level and only draws from
**levels that have unlocked** based on `CHANNEL_START_DATE` in `config.py`.

When a higher level unlocks, the channel doesn't abandon the old level — it
shifts the *bias* toward the new one (`LATEST_LEVEL_BIAS = 70%`) while still
giving 30% of slots to older levels for variety.

## Phase timeline

| Phase | Day range | Months | Level | Words/day | Notes |
|---|---|---|---|---|---|
| **1** | 1–120 | 1–4 | N5 only | 4 | Beginner foundation. Cover ~500 N5 words. |
| **2** | 121–240 | 5–8 | N4 (70%) + N5 (30%) | 4 | N4 takes over, N5 stays as review. |
| **3** | 241–540 | 9–18 | N3 (70%) + N4/N5 (30%) | 4 | Intermediate vocabulary dominates. |
| **4** | 541–900 | 19–30 | N2 (70%) + N3/N4 (30%) | 4 | Upper intermediate. |
| **5** | 901+ | 31+ | N1 (70%) + N2/N3 (30%) | 4 | Advanced. ~7 years of N1 alone. |

## Current word counts (as of last update)

| Level | Word count | Days at 4/day | Status |
|---|---|---|---|
| N5 | ~500 | ~125 | ✅ Loaded |
| N4 | ~100 | ~25 | ⚠️ Needs expansion before day 121 unlock |
| N3 | ~100 | ~25 | ⚠️ Needs expansion before day 241 unlock |
| N2 | 0 | 0 | ❌ To add before day 541 |
| N1 | 0 | 0 | ❌ To add before day 901 |

**Action items**: Expand N4 to ~600 words by month 3, N3 to ~800 by month 6,
N2 to ~1500 by month 17, N1 to ~3000 by month 29. (We don't need the full
JLPT lists — ~30% of the official list is enough for 4-month dwell.)

## Themed expansion batches (orthogonal to JLPT)

These get sprinkled in as "cultural" / "interesting word" picks to keep CTR
high. Add when the channel feels stale or for seasonal pushes:

| Theme | Approx. word count | Best time to release |
|---|---|---|
| Food vocabulary | 500 | Anytime — high CTR |
| Travel vocab | 300 | Spring (sakura tourism season) |
| Workplace / business | 400 | January (new fiscal year in Japan) |
| Anime / manga vocabulary | 300 | Anytime — drives strong fan engagement |
| Seasonal: cherry blossom | 100 | March / April |
| Seasonal: summer festival | 100 | July / August |
| Seasonal: autumn | 100 | September / October |
| Seasonal: New Year | 100 | December / January |
| Slang & casual speech | 300 | Once channel is ~6 months old |
| Idioms (慣用句) | 500 | After N3 unlocks |
| 4-character compounds (四字熟語) | 400 | After N2 unlocks |
| Loan words (外来語) | 200 | Anytime — fun, easy |

## Adding more words

1. Open `words.txt`
2. Find the right `# ===== LEVEL: NX =====` section
3. Append the new word(s) on their own line
4. Commit and push — picker will include them in its next pool computation

The picker is deterministic and dedup-aware, so adding words mid-cycle doesn't
break anything — they just enter the rotation.

## Tuning the schedule

Want a faster/slower curriculum? Edit `LEVEL_UNLOCK_DAYS` in `config.py`:

```python
LEVEL_UNLOCK_DAYS = {
    "N5":   0,
    "N4":   120,   # ← lower to unlock N4 sooner
    "N3":   240,
    "N2":   540,
    "N1":   900,
}
```

Want N4 to take over more aggressively when it unlocks? Raise
`LATEST_LEVEL_BIAS` (currently 0.70 = 70%).

## Long-term content sources

When the curated lists run out (10+ years from now), you have:

- **Newsworthy words** — Japan publishes 流行語大賞 (buzzword of the year) annually
- **Loan-word adoption** — new English borrowings enter Japanese every year
- **Regional dialects (方言)** — Kansai-ben, Hakata-ben, etc. — each has 100s of unique terms
- **Subculture vocabulary** — gaming, idol, fashion, internet — constantly evolving
- **Historical / classical** — 古文 vocabulary if you ever pivot to advanced learners

The channel will not run out of vocabulary. The bottleneck is curation, not
supply.
