# Retention Radar

![Retention Radar](preview.png)

Longevity clinic members see their clinic 3 to 6 times a year. The other 320 days are where they quietly drift. Most churn lands around month 11. Each lost member is $15k to $50k a year.

Clinics watch logins and NPS. Neither predicts renewal. Retention Radar watches the signals that do.

**Live demo:** open `index.html` in any browser. Every member in it is simulated.

## What it does

- Flags members who are drifting, weeks before renewal
- Shows exactly why with plain rules
- Drafts a check-in in the coach's voice. One tap to send.
- Puts a dollar figure on renewals at risk

## The rules

| Signal | Points |
|---|---|
| Wearable stops syncing 7+ days / 14+ days | 15 / 30 |
| 1 message unanswered / 2 or more | 8 / 20 |
| Habit score down 10+ / 25+ points | 10 / 20 |
| Missed lab draw | 15 |
| No coach call 60+ / 90+ days | 8 / 15 |

**Needs care** at 55+. **Drifting** at 30+. Anyone drifting with a renewal inside 60 days counts toward the at-risk total.

Rules first, not a model. A 200 member clinic doesn't lose enough people a year to train one. Every flag can be explained to a coach.

## Run it

No build step. One self contained HTML file.

```
git clone https://github.com/DrDanXD/retention-radar
open retention-radar/index.html
```

## Roadmap

- Pull real wearable data (Garmin, Oura, Whoop)
- Connect to the clinic's messaging and lab booking tools
- Weekly at-risk digest for founders

## Run a longevity clinic?

I'm looking for a few clinics to pilot this on real data. Email dsriniv8@jh.edu or DM me on X.
