# Conversation Failure-Mode Spec

> **Purpose**: Adversarial conversation scripts that stress ambiguity,
> correction, chained what-ifs, partial resets, contradictory input, and
> missed confirmations. Each script specifies the expected assistant
> behaviour. The regression harness (Prompt 12) replays these scripts and
> asserts the outcomes.
>
> **Reference**: docs/dev/conversation-design.md for the happy-path templates
> and voice rules. This document covers the ugly paths.

---

## How to read each scenario

```
Turn N  [USER]       what the user types
        [EXPECTED]   what the assistant must do (state, content rules, card)
        [MUST NOT]   things the assistant must never do in this turn
        [WHY]        the failure mode being tested
```

The `[EXPECTED]` block describes behaviour constraints, not exact text.
The regression harness asserts these constraints with pattern matching.

---

## FM-01 — Immediate correction of a just-confirmed fact

The user provides a fact, the assistant confirms it, and the user
immediately contradicts the confirmation.

```
Turn 1  [USER]       Can I export HS 110311 from Ghana to Nigeria?
        [EXPECTED]   State: COLLECTING → ASSESSING → RESULT.
                     Confirms all facts. Runs assessment.
                     assessment.hs6_code == "110311", exporter == GHA.

Turn 2  [USER]       Wait, not Ghana. I meant Cameroon.
        [EXPECTED]   State: COLLECTING.
                     Override exporter from GHA to CMR.
                     accumulated_context.known_facts.exporter == "CMR".
                     importer remains NGA. hs6_code remains "110311".
                     Since all facts are now present, proceed to ASSESSING → RESULT.
                     New evaluation_id, different from Turn 1.
        [MUST NOT]   Must not ask "which country?" — user already said Cameroon.
                     Must not keep GHA in accumulated facts.
                     Must not re-ask for hs6_code or importer.
        [WHY]        Tests fact override after a completed assessment. The
                     correction arrives AFTER the engine already ran with
                     the wrong value.
```

---

## FM-02 — Contradictory exporter and importer (same country)

```
Turn 1  [USER]       Check HS 110311 from Nigeria to Nigeria
        [EXPECTED]   State: ERROR or CLARIFYING.
                     Must not submit to engine with exporter == importer.
                     Ask: "The exporting and importing country can't be the
                     same. Which country are you exporting to?"
        [MUST NOT]   Must not run the engine with NGA→NGA.
                     Must not crash.
        [WHY]        Tests same-country validation before engine call.
```

---

## FM-03 — HS code that looks valid but doesn't exist

```
Turn 1  [USER]       Check HS 999999 from Ghana to Nigeria
        [EXPECTED]   State: ERROR.
                     Error code: CLASSIFICATION_ERROR.
                     Message per conversation-design.md §3.8.
                     accumulated_context preserves exporter=GHA, importer=NGA.

Turn 2  [USER]       Oh sorry, it's 110311
        [EXPECTED]   State: COLLECTING.
                     Override hs6_code from "999999" to "110311".
                     Exporter and importer still present from Turn 1.
                     Proceed to ASSESSING → RESULT.
        [MUST NOT]   Must not re-ask for countries.
                     Must not carry the error forward.
        [WHY]        Tests error recovery with fact preservation. The invalid
                     HS code should be replaceable without losing corridor facts.
```

---

## FM-04 — Unsupported corridor after facts collected

```
Turn 1  [USER]       110311

Turn 2  [USER]       From Ghana to South Africa
        [EXPECTED]   State: ERROR.
                     Error code: CORRIDOR_NOT_SUPPORTED.
                     Message lists supported countries.
                     accumulated_context keeps hs6_code=110311.

Turn 3  [USER]       OK, try Nigeria instead
        [EXPECTED]   State: COLLECTING.
                     Ambiguous: "Nigeria instead" — instead of which country?
                     If exporter was GHA (from "Ghana to South Africa"),
                     override importer to NGA.
                     If intent is ambiguous, ask: "Do you mean exporting from
                     Ghana to Nigeria?"
        [MUST NOT]   Must not guess if both exporter and importer are ambiguous.
        [WHY]        Tests corridor error recovery with ambiguous correction.
```

---

## FM-05 — Chained what-ifs: three countries in sequence

```
Turn 1  [USER]       Check HS 110311, Ghana to Nigeria, 2025
        [EXPECTED]   RESULT. evaluation_id = E1.

Turn 2  [USER]       What if from Cameroon?
        [EXPECTED]   WHAT-IF. Override exporter to CMR.
                     New evaluation_id = E2 ≠ E1.
                     Comparison: "Compared to your previous check (from Ghana):"

Turn 3  [USER]       And what about from Senegal?
        [EXPECTED]   WHAT-IF. Override exporter to SEN.
                     New evaluation_id = E3 ≠ E2 ≠ E1.
                     Comparison against E2 (Cameroon), NOT E1 (Ghana).
                     "Compared to your previous check (from Cameroon):"
        [MUST NOT]   Must not compare to the original E1.
                     Must not lose importer (NGA) or year (2025) or hs6_code.

Turn 4  [USER]       Go back to the Ghana one
        [EXPECTED]   State: FOLLOW-UP.
                     Show the E1 assessment result from history.
                     Do NOT re-run the engine. E1 already exists.
        [MUST NOT]   Must not create a fourth evaluation.
                     Must not claim the Ghana result is "new".
        [WHY]        Tests chained what-ifs with correct comparison anchoring,
                     plus backward reference to an earlier result without re-run.
```

---

## FM-06 — What-if that changes two facts at once

```
Turn 1  [USER]       Check HS 110311, Ghana to Nigeria
        [EXPECTED]   RESULT. E1.

Turn 2  [USER]       What about 180631 from Cameroon?
        [EXPECTED]   WHAT-IF. Override hs6_code to "180631" AND exporter to CMR.
                     New evaluation_id = E2.
                     Comparison header shows BOTH changes:
                     "Product: 110311 → 180631, Exporter: Ghana → Cameroon"
        [MUST NOT]   Must not ask for the changes separately.
                     Must not only apply one of the two changes.
        [WHY]        Tests multi-field mutation in a single what-if turn.
```

---

## FM-07 — Partial reset: "start over" but with a caveat

```
Turn 1  [USER]       Check HS 110311, Ghana to Nigeria
        [EXPECTED]   RESULT.

Turn 2  [USER]       Start over
        [EXPECTED]   State: WELCOME or COLLECTING (empty).
                     "Starting fresh. What would you like to check?"
                     accumulated_context.known_facts is empty.

Turn 3  [USER]       Same product, but to Cameroon this time
        [EXPECTED]   State: CLARIFYING.
                     "Same product" is ambiguous after a reset — the assistant
                     does NOT have 110311 in context anymore.
                     Must ask for the HS code.
        [MUST NOT]   Must not assume "same product" means 110311.
                     Must not silently recover cleared facts.
        [WHY]        Tests that "start over" truly clears all state, even
                     when the user implies continuity with "same product".
```

---

## FM-08 — User provides facts in a language-ambiguous way

```
Turn 1  [USER]       chocolate from ivory coast
        [EXPECTED]   State: COLLECTING → CLARIFYING.
                     Recognise "ivory coast" → CIV (Côte d'Ivoire).
                     "chocolate" is ambiguous — no specific HS code.
                     Must ask: "There are several HS codes for chocolate
                     products — for example, 180631 for filled chocolate or
                     180620 for chocolate preparations. Do you know the
                     6-digit HS code?"
                     accumulated_context: exporter=CIV, importer=missing,
                     hs6_code=missing.
        [MUST NOT]   Must not guess an HS code for "chocolate".
                     Must not reject "ivory coast" as unrecognised.
        [WHY]        Tests country name alias resolution and product ambiguity
                     handling per conversation-design.md §4.3.
```

---

## FM-09 — User provides numbers that could be HS code or year

```
Turn 1  [USER]       Check 202511 from Ghana to Nigeria
        [EXPECTED]   State: COLLECTING → ASSESSING or CLARIFYING.
                     "202511" is 6 digits — treat as HS code.
                     If "202511" does not resolve → CLASSIFICATION_ERROR.
                     Do NOT interpret as year 2025 + "11".
        [MUST NOT]   Must not split the number into year + partial code.
                     Must not silently assume year=2025.
        [WHY]        Tests numeric ambiguity — 6-digit strings are always
                     treated as HS codes, never as concatenated year+fragment.
```

---

## FM-10 — Year provided as relative reference

```
Turn 1  [USER]       Check 110311, Ghana to Nigeria, next year
        [EXPECTED]   State: COLLECTING.
                     Resolve "next year" to 2027 (current year 2026 + 1).
                     Confirm: "Got it — HS 110311 (wheat groats), exporting
                     from Ghana to Nigeria. I'll check for 2027 — let me
                     know if you meant a different year."
        [MUST NOT]   Must not leave year as the string "next year".
                     Must not skip the confirmation.
        [WHY]        Tests relative date resolution per conversation-design.md §4.3.
```

---

## FM-11 — User corrects the assistant's year assumption

```
Turn 1  [USER]       Check 110311, Ghana to Nigeria
        [EXPECTED]   Auto-defaults year to 2026.
                     "I'll check for 2026."

Turn 2  [USER]       No, 2025
        [EXPECTED]   State: COLLECTING.
                     Override year from 2026 to 2025.
                     Re-run assessment with year=2025.
                     New evaluation_id (different from Turn 1 if Turn 1
                     produced one).
        [MUST NOT]   Must not keep year=2026.
                     Must not ask "which year?" — user already said 2025.
        [WHY]        Tests correction of the auto-default year assumption.
```

---

## FM-12 — User says "yes" to a clarification but provides no fact

```
Turn 1  [USER]       I want to export from Ghana
        [EXPECTED]   COLLECTING + CLARIFYING.
                     "Got it — exporting from Ghana."
                     Ask for hs6_code and importer.

Turn 2  [USER]       Yes
        [EXPECTED]   State: CLARIFYING.
                     "Yes" provides no new facts.
                     Re-ask the same missing facts, perhaps rephrased:
                     "I still need the 6-digit HS code and the destination
                     country. Could you provide those?"
        [MUST NOT]   Must not treat "yes" as a fact value.
                     Must not crash or produce an empty assessment.
                     Must not clear existing facts (exporter=GHA still present).
        [WHY]        Tests empty/non-informative user input handling.
```

---

## FM-13 — User provides exporter but not importer, then provides importer only

```
Turn 1  [USER]       110311 from Ghana
        [EXPECTED]   COLLECTING + CLARIFYING.
                     accumulated: hs6_code=110311, exporter=GHA.
                     Ask for importer.

Turn 2  [USER]       Nigeria
        [EXPECTED]   State: COLLECTING.
                     "Nigeria" in context of a missing importer → importer=NGA.
                     Do NOT override exporter to NGA.
                     All facts now present → ASSESSING → RESULT.
        [MUST NOT]   Must not interpret "Nigeria" as exporter (exporter is
                     already set to GHA).
        [WHY]        Tests contextual disambiguation — a single country name
                     binds to the missing slot, not the most recent slot.
```

---

## FM-14 — User provides both countries but swapped

```
Turn 1  [USER]       110311 from Nigeria to Ghana
        [EXPECTED]   RESULT. exporter=NGA, importer=GHA.
                     (NGA→GHA is a supported corridor.)

Turn 2  [USER]       I got that backwards. It's Ghana to Nigeria.
        [EXPECTED]   State: COLLECTING.
                     Override exporter to GHA, importer to NGA.
                     Re-run assessment. New evaluation_id.
        [MUST NOT]   Must not keep the old exporter/importer.
                     Must not ask "which one did you mean to change?"
        [WHY]        Tests explicit correction of both countries simultaneously.
```

---

## FM-15 — What-if to an unsupported corridor

```
Turn 1  [USER]       Check 110311, Ghana to Nigeria
        [EXPECTED]   RESULT. E1.

Turn 2  [USER]       What if I exported to South Africa?
        [EXPECTED]   State: ERROR.
                     CORRIDOR_NOT_SUPPORTED for GHA→ZAF.
                     accumulated_context retains hs6_code=110311, exporter=GHA.
                     importer is now ZAF (the failed attempt).
                     "This country pair isn't supported yet."

Turn 3  [USER]       OK never mind, back to Nigeria
        [EXPECTED]   State: COLLECTING.
                     Override importer to NGA.
                     All facts present → re-run. New evaluation_id E3.
                     Should produce same outcome as E1 (same inputs).
        [MUST NOT]   Must not lose hs6_code or exporter after the corridor error.
        [WHY]        Tests what-if into an unsupported corridor and recovery.
```

---

## FM-16 — Rapid-fire facts with no punctuation

```
Turn 1  [USER]       110311 ghana nigeria 2025
        [EXPECTED]   State: COLLECTING → ASSESSING → RESULT.
                     Parse all four facts from a single unpunctuated line.
                     hs6_code=110311, exporter=GHA, importer=NGA, year=2025.
        [MUST NOT]   Must not ask for clarification if all four facts are
                     unambiguously present.
        [WHY]        Tests the extractor on terse, unpunctuated, all-lowercase
                     input.
```

---

## FM-17 — User asks an out-of-scope question mid-conversation

```
Turn 1  [USER]       Check 110311, Ghana to Nigeria
        [EXPECTED]   RESULT.

Turn 2  [USER]       How long does customs clearance take?
        [EXPECTED]   State: OUT-OF-SCOPE.
                     "I can help with AfCFTA eligibility checks, tariff rates,
                     and evidence requirements. I'm not able to help with
                     customs clearance timelines."
                     accumulated_context is PRESERVED — not cleared.

Turn 3  [USER]       What if from Cameroon?
        [EXPECTED]   WHAT-IF. Uses preserved context (hs6_code=110311,
                     importer=NGA, year=2025). Override exporter to CMR.
                     New assessment.
        [MUST NOT]   Must not have lost context after the out-of-scope turn.
        [WHY]        Tests that out-of-scope turns do not corrupt or clear
                     accumulated context.
```

---

## FM-18 — User provides conflicting HS codes in the same message

```
Turn 1  [USER]       Is 110311 or 180631 eligible from Ghana to Nigeria?
        [EXPECTED]   State: CLARIFYING.
                     Two HS codes in one message — ambiguous.
                     "You mentioned two HS codes (110311 and 180631). Which
                     product would you like me to check first?"
                     accumulated_context: exporter=GHA, importer=NGA.
                     hs6_code is NOT set (ambiguous).
        [MUST NOT]   Must not pick one silently.
                     Must not run two assessments in one turn.
        [WHY]        Tests multi-value ambiguity for a single field.
```

---

## FM-19 — User repeats the same what-if they already ran

```
Turn 1  [USER]       Check 110311, Ghana to Nigeria
        [EXPECTED]   RESULT. E1.

Turn 2  [USER]       What if from Cameroon?
        [EXPECTED]   WHAT-IF. E2.

Turn 3  [USER]       What if from Cameroon?
        [EXPECTED]   State: FOLLOW-UP or WHAT-IF.
                     The system may either:
                     (a) Detect duplicate and say "You already checked Cameroon
                         in your previous turn. Here are those results:" and
                         reference E2 without re-running.
                     (b) Re-run the assessment (idempotent, same inputs → same
                         outcome). E3 will have a new evaluation_id but the
                         same eligible/pathway outcome as E2.
                     Either behaviour is acceptable.
        [MUST NOT]   Must not crash or produce an error.
                     If option (b): must not claim the result is different from
                     E2 when it is not.
        [WHY]        Tests idempotency of what-if turns.
```

---

## FM-20 — Extremely long user input

```
Turn 1  [USER]       [A 1500-character message describing their export business,
                     supply chain, certifications, packaging, and asking about
                     HS 110311 from Ghana to Nigeria with details about their
                     ex-works value and non-originating inputs.]
        [EXPECTED]   State: COLLECTING → ASSESSING → RESULT.
                     Extract the relevant facts: hs6_code=110311, exporter=GHA,
                     importer=NGA.
                     Ignore the business narrative — it is not a trade fact.
        [MUST NOT]   Must not echo back the full 1500-character input.
                     Must not treat narrative content as trade facts.
                     Must not reject the input (under 2000-char limit).
        [WHY]        Tests fact extraction from verbose, noisy input.
```

---

## FM-21 — User sends empty or whitespace-only messages

```
Turn 1  [USER]       [empty string or whitespace]
        [EXPECTED]   State: CLARIFYING or WELCOME (if first turn).
                     "I didn't catch that. What product would you like to
                     check for AfCFTA eligibility?"
                     accumulated_context unchanged.
        [MUST NOT]   Must not crash.
                     Must not clear accumulated facts.
                     Must not create an assessment.
        [WHY]        Tests empty input handling.
```

---

## FM-22 — User provides country ISO code instead of name

```
Turn 1  [USER]       110311 GHA NGA
        [EXPECTED]   State: COLLECTING → ASSESSING → RESULT.
                     Parse GHA as exporter, NGA as importer.
                     hs6_code=110311, exporter=GHA, importer=NGA.
        [MUST NOT]   Must not reject ISO codes.
                     Must not treat "GHA" as an unknown word.
        [WHY]        Tests that both country names and ISO codes are accepted.
```

---

## FM-23 — What-if changes the HS code, which then fails classification

```
Turn 1  [USER]       Check 110311, Ghana to Nigeria
        [EXPECTED]   RESULT. E1.

Turn 2  [USER]       What if the product was 888888?
        [EXPECTED]   State: ERROR.
                     CLASSIFICATION_ERROR for HS 888888.
                     accumulated_context: exporter=GHA, importer=NGA,
                     hs6_code=888888 (the failed attempt).

Turn 3  [USER]       Try 180631 instead
        [EXPECTED]   State: COLLECTING.
                     Override hs6_code to 180631.
                     exporter=GHA, importer=NGA still present.
                     ASSESSING → RESULT. E3.
        [MUST NOT]   Must not revert to 110311 after the error.
                     Must not lose corridor facts.
        [WHY]        Tests what-if → classification error → recovery chain.
```

---

## FM-24 — User asks "is this guaranteed?" after an eligible result

```
Turn 1  [USER]       Check 110311, Ghana to Nigeria
        [EXPECTED]   RESULT. Eligible.

Turn 2  [USER]       So this is guaranteed to clear customs?
        [EXPECTED]   State: FOLLOW-UP.
                     "This assessment is based on the published AfCFTA rules
                     and the facts you provided. It does not constitute a
                     customs ruling or legal guarantee. You should confirm
                     with your customs authority before shipment."
        [MUST NOT]   Must not say "yes" or "guaranteed".
                     Must not re-run the engine.
        [WHY]        Tests the certainty disclaimer per conversation-design.md §3.6.
```

---

## FM-25 — User provides facts that contradict the assessment they just saw

```
Turn 1  [USER]       Check 110311, Ghana to Nigeria
        [EXPECTED]   RESULT. eligible=true.

Turn 2  [USER]       But my product doesn't qualify
        [EXPECTED]   State: FOLLOW-UP.
                     "The assessment is based on the published rules and the
                     facts you provided. If the real-world situation differs
                     from what was entered — for example, if the non-originating
                     inputs don't actually shift heading — the result may not
                     apply. Would you like to re-check with different facts?"
        [MUST NOT]   Must not change the assessment outcome.
                     Must not say "you're right, it doesn't qualify".
                     Must not re-run the engine with the same facts.
        [WHY]        Tests that user disagreement does not override the
                     deterministic engine outcome.
```

---

## FM-26 — Mid-conversation session expiry simulation

```
Turn 1  [USER]       Check 110311, Ghana to Nigeria
        [EXPECTED]   RESULT.

        [24 hours pass — session expires]

Turn 2  [USER]       What if from Cameroon?
        [EXPECTED]   State: ERROR.
                     HTTP 410 Gone.
                     "This conversation has expired. Please start a new one."
        [MUST NOT]   Must not return partial data.
                     Must not silently create a new session.
        [WHY]        Tests session TTL enforcement.
```

---

## FM-27 — User provides the same fact twice in different forms

```
Turn 1  [USER]       Export from Ghana
        [EXPECTED]   COLLECTING. exporter=GHA.

Turn 2  [USER]       From Accra
        [EXPECTED]   State: COLLECTING or CLARIFYING.
                     "Accra" is not a recognised country name in V01_COUNTRIES.
                     If mapped to Ghana (city → country), exporter stays GHA.
                     If not mapped, ignore it and do NOT override exporter.
                     In either case, must not set exporter to "Accra".
        [MUST NOT]   Must not treat "Accra" as a country code.
                     Must not clear exporter=GHA.
        [WHY]        Tests city-name input that could be confused with a
                     country override.
```

---

## FM-28 — User sends a what-if before any assessment exists

```
Turn 1  [USER]       What if I exported from Ghana?
        [EXPECTED]   State: COLLECTING.
                     Treat as a normal fact: exporter=GHA.
                     No prior assessment to compare against.
                     Do NOT show a comparison header.
                     Ask for remaining missing facts.
        [MUST NOT]   Must not crash trying to load a "previous assessment".
                     Must not show "Compared to your previous check:".
        [WHY]        Tests what-if phrasing when there is no prior result.
```

---

## Summary: Failure Mode Coverage Matrix

| ID | Category | Key behaviour tested |
|----|----------|---------------------|
| FM-01 | Correction | Fact override after completed assessment |
| FM-02 | Validation | Same-country exporter/importer rejection |
| FM-03 | Error recovery | Invalid HS code → correction with preserved corridor |
| FM-04 | Error recovery | Unsupported corridor → ambiguous correction |
| FM-05 | Chained what-if | Three sequential overrides, correct comparison anchor |
| FM-06 | What-if | Multi-field mutation in single turn |
| FM-07 | Partial reset | "Start over" clears all state, "same product" is ambiguous |
| FM-08 | Ambiguity | Product name and country alias resolution |
| FM-09 | Ambiguity | 6-digit number always treated as HS code, not year |
| FM-10 | Ambiguity | Relative date resolution with confirmation |
| FM-11 | Correction | Override auto-defaulted year |
| FM-12 | Empty input | "Yes" provides no facts |
| FM-13 | Disambiguation | Single country name binds to missing slot |
| FM-14 | Correction | Both countries swapped, corrected together |
| FM-15 | What-if + error | What-if into unsupported corridor and recovery |
| FM-16 | Parsing | Terse, unpunctuated, all-lowercase input |
| FM-17 | Scope | Out-of-scope turn preserves context |
| FM-18 | Ambiguity | Two HS codes in one message |
| FM-19 | Idempotency | Duplicate what-if |
| FM-20 | Parsing | Fact extraction from verbose noisy input |
| FM-21 | Empty input | Empty or whitespace-only message |
| FM-22 | Parsing | ISO codes instead of country names |
| FM-23 | What-if + error | What-if HS fails classification → recovery |
| FM-24 | Scope | Certainty disclaimer after eligible result |
| FM-25 | Boundary | User disagreement does not override engine |
| FM-26 | Session | TTL expiry returns 410 |
| FM-27 | Parsing | City name does not override country |
| FM-28 | What-if edge | What-if phrasing with no prior assessment |
