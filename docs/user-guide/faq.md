# FAQ

## Is this legal advice?

No.

AIS is a deterministic decision-support system.
It evaluates the facts you provide against the loaded rules and returns a structured result.

It does not replace:

- legal advice
- customs advice
- a ruling from the competent authority

You should treat it as a structured compliance tool, not as a legal opinion.

## Can I trust the results?

You can trust AIS to do one thing well:

- apply the loaded rules consistently and explain the result in a structured way

You should still verify the result by:

- checking the rule status
- reviewing the audit trail
- confirming the supporting documents
- verifying with the relevant competent authority where necessary

The key strength of AIS is that every result traces back to specific legal logic and stored legal text.

## Why does it say “provisional”?

`provisional` means the legal or schedule basis is not fully settled.

That usually means:

- the rule exists, but is not treated as fully agreed
- or the tariff schedule is still provisional

You should read provisional results as:

> useful decision support, but not the strongest possible legal footing

## Why does it say “incomplete”?

`incomplete` means the system did not have enough complete footing for a settled result.

Usually that means:

- key facts were missing
- or an operational blocker prevented a full assessment

It does not mean the product definitely fails.
It means AIS needs more information or a firmer legal/operational footing.

## What if my HS code isn’t found?

If the HS code is not found:

- check that you supplied at least 6 digits
- verify the first 6 digits of your classification
- confirm the correct HS version

AIS computes at HS6 level in v0.1.
If you send HS8 or HS10, it truncates to the first 6 digits for computation.

## What production facts do I need?

That depends on the rule pathway.

Common examples:

- **CTH**: input heading and output heading
- **VNM**: ex-works value and non-originating value
- **WO**: facts showing the product is wholly obtained
- **Direct transport**: whether the goods moved under direct transport or permitted transit

The easiest way to see what AIS needed is to check:

- `missing_facts`

That field tells you exactly what information was absent.

## What’s the difference between CTH, VNM, VA, and WO?

### CTH

**Change in tariff heading**

The non-originating input and the finished product must fall under different 4-digit headings.

### VNM

**Value of non-originating materials**

The value of non-originating materials must stay at or below a legal threshold.

### VA

**Value added**

The regional or local value contribution must reach a required threshold.

### WO

**Wholly obtained**

The product must be wholly obtained in the territory, rather than merely processed there.

## Can I use this for customs declarations?

No.

AIS is not a customs declaration system.
It is a decision-support engine that helps you understand whether a claim appears supportable under the loaded rules.

You still need:

- the actual declaration workflow
- the required supporting documents
- authority review where applicable

## How current is the data?

AIS uses the legal and tariff data loaded into the current deployment.

That means:

- it is only as current as the dataset loaded into the system
- it does not provide real-time legal updates in v0.1

If freshness matters for your use case, verify the underlying legal source and competent-authority position before relying on the result operationally.

## Who maintains this system?

AIS is maintained by the project team operating the current deployment.

In practice, maintenance includes:

- loading rule and tariff data
- updating status-aware legal records
- maintaining the audit and evidence layers
- expanding corridor and country coverage over time

For operational questions, treat the deployment owner or program team as the maintainer of record.
