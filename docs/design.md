# Design notes

## Rules first, not a model

A clinic with 200 members and 20% annual churn loses about 40 people a year. That is not enough labelled churn to train a model that generalises, and a model that cannot explain itself is hard for a coach to act on. "Elena's score went up" is useless. "Elena's watch hasn't synced in 16 days and two of your messages are unanswered" tells the coach what to say.

So version 0.1 is a transparent points system. Each signal is a pure function in `signals.py`, every threshold lives in `config.py`, and each flag carries the reasons that produced it. Once a clinic has a few years of renewal outcomes, the same signals become features for a calibrated model. The rules then serve as the baseline it has to beat.

## The five signals

| Signal | Why it matters | Points |
|---|---|---|
| Wearable gap | The device is the program's daily touchpoint. A silent device usually means a member who has stepped away. | 7+ days: 15. 14+ days: 30 |
| Unanswered coach messages | Engagement with the human side of the program. One unread note is noise. Several is a pattern. | 1: 8. 2+: 20 |
| Habit slip | Drop in adherence over the last 14 days compared with the 28 days before. Days with no log count as zero, because silence is not stability. | 10+ points: 10. 25+ points: 20 |
| Missed lab draw | A booked draw that never happened in the last 30 days. Labs are the visible proof of value in most programs. | 15 |
| Coach gap | Days since the last live conversation. | 60+ days: 8. 90+ days: 15 |

Bands: **Needs care** at 55 and up, **Drifting** at 30 and up, otherwise **Steady**. The dollar figure counts flagged members whose renewal falls in the next 60 days.

## No leaking the future

Every signal takes an `as_of` date and ignores anything after it. A sync tomorrow cannot hide a gap today, and a reply next week does not count as answered now. The backtest relies on this, and there are tests for it.

## Replies are conversation level

A member message answers every coach message before it. If a member replies to the latest note, they are engaged, even if they skipped an earlier one. "Unanswered" therefore means the member went quiet. The CSV adapter and the simulator use the same rule (`pair_replies`), and a test checks that a clinic exported to CSV and loaded back scores identically.

## Choosing the threshold

The cut-off for Drifting is a coach workload decision, not a statistical one. In the default synthetic scenario:

| Cut-off | Precision | Recall | Members flagged |
|---|---|---|---|
| 15 | 74% | 86% | 24% |
| 20 | 85% | 80% | 19% |
| 25 | 91% | 57% | 13% |
| 30 (default) | 96% | 41% | 9% |

A cut-off of 20 catches about twice as many leavers as 30, at the cost of flagging twice as many members. The default stays at 30 because it was set before the backtest. Tuning it on synthetic data would only fit the simulator. A real clinic should pick the cut-off from its own history and from how many check-ins its coaches can handle in a week.

## Drafts

`drafts.py` asks Claude for a short, warm message from the member's top signals, with a strict system prompt: no scores, no mention of tracking, no medical advice. Without an API key, or if the call fails, a deterministic template is used, so the pipeline never blocks on a model. The coach always approves before anything is sent.

## Known limits

* **Strava only sees workouts.** A member who wears a ring for sleep but stops working out looks quieter on Strava than they are. Pair it with a daily summary export when you can.
* **No seasonality.** Holidays and travel produce real gaps. The simulator includes travel gaps for that reason, but the rules do not yet know a member's calendar.
* **New members.** Habit slip needs 5 logged days of baseline, so it stays silent for roughly the first six weeks.
* **The backtest is synthetic.** See [backtest.md](backtest.md).
