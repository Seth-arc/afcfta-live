# Rules Of Origin

This document explains the rules-of-origin concepts that AIS applies.

It is written for people who already work with trade documents or customs
processes, but who may not have studied the AfCFTA Protocol on Rules of Origin
in detail.

## What Rules Of Origin Are

**Rules of origin** are the legal tests used to decide whether a product counts
as originating in a country or trade area for a particular purpose.

In the AfCFTA context, they answer:

> Does this product qualify for AfCFTA preferential treatment?

They matter because tariff preferences are not available simply because goods
are shipped from one country to another.
The goods must meet the legal origin conditions.

## Why Rules Of Origin Exist

Rules of origin exist to prevent simple transshipment or minimal processing from
claiming benefits that were intended for genuinely qualifying production.

They help answer questions like:

- Was there substantial transformation?
- Was enough local or regional content added?
- Was the product wholly obtained?
- Was a specific required process performed?

## Preferential vs Non-Preferential Origin

There are two broad origin concepts.

### Preferential Origin

**Preferential origin** determines whether a product qualifies for a reduced or
zero tariff under a trade agreement, such as the AfCFTA.

This is what AIS evaluates.

### Non-Preferential Origin

**Non-preferential origin** is used for other purposes, such as general customs
treatment, trade remedies, marking, or statistics.

AIS is not a general non-preferential origin engine.
It is focused on AfCFTA preferential origin decision support.

## Product-Specific Rules vs General Rules

AfCFTA origin decisions have two important layers.

### Product-Specific Rules

These are the **Appendix IV** rules tied to particular products or product groups.

Examples:

- a change in tariff heading
- a value threshold
- a specific processing requirement

These rules answer:

> What legal test applies to this product?

### General Rules

These are broader origin rules that apply across products.

Important examples:

- insufficient operations
- cumulation
- direct transport

These rules answer:

> Even if the product-specific rule is satisfied, is there any broader rule that still prevents origin from being recognized?

AIS keeps these layers separate on purpose.
A product can pass its product-specific rule and still fail a general rule.

## Main Rule Types

## WO: Wholly Obtained

**WO** means **wholly obtained**.

This usually applies where the product is entirely obtained or produced in one
country without relying on imported non-originating materials in a way that
breaks the rule.

Typical examples:

- crops grown in one country
- animals born and raised there
- fish caught under qualifying conditions

In plain terms:

> The product is treated as originating because it was entirely obtained there.

## CTH: Change In Tariff Heading

**CTH** means **change in tariff heading**.

A **tariff heading** is the first 4 digits of the product classification.

Under a CTH rule, the system asks:

> Are the non-originating inputs in a different 4-digit heading from the finished product?

Example:

- input heading: `1001`
- finished product heading: `1103`

Because the headings differ, the CTH test can pass.

## VNM: Value Of Non-Originating Materials

**VNM** means **value of non-originating materials**.

This rule limits how much imported or non-originating content may remain in the product.

In plain terms:

> The product can qualify only if the non-originating portion stays at or below the legal threshold.

AIS evaluates this using the factual values provided, such as:

- ex-works value
- non-originating value

## VA: Value Added

**VA** means **value added**.

This looks at how much domestic or regional value has been added during production.

In plain terms:

> The product can qualify only if enough value was created locally or regionally.

This is similar to VNM in that it uses value calculations, but it measures the
originating or local contribution rather than the ceiling on imported content.

## PROCESS: Specific Process

Some rules require a specific manufacturing or processing step.

In plain terms:

> The product qualifies only if a particular process was performed.

This is common where tariff shift or value rules are not considered sufficient
on their own.

## What “Or” Means In Appendix IV

Sometimes a product rule offers alternative legal routes.

Example idea:

- `CTH` **or**
- `VNM <= 50%`

That means the product can qualify through either route.

AIS models these as **alternative pathways**.

Operational meaning:

- if the first pathway fails, the next one can still be tried
- first passing pathway wins

## What “And” Means

Within a single pathway, conditions may accumulate.

Example idea:

- `CTH` **and**
- `VNM <= 60%`

That means both requirements must be satisfied together.

Operational meaning:

- one failed condition means the pathway fails

## General Rules

These are not the same as the product-specific pathway itself.

## Insufficient Operations

Some minimal operations never confer origin on their own.

Examples can include very light or simple operations that do not amount to
substantial transformation.

AIS treats this as a separate check because:

- a product might appear to satisfy a technical pathway
- but still fail because the underlying operation was legally insufficient

## Cumulation

**Cumulation** allows qualifying materials from another AfCFTA state party to be
treated as originating under certain conditions.

In plain terms:

> Origin can sometimes be built across participating states, not only inside one state.

But cumulation is not automatic.
AIS checks whether:

- cumulation was claimed
- the selected pathway allows it
- the factual conditions support it

## Direct Transport

Direct transport addresses how the goods move from exporter to importer.

In plain terms:

> Even if the product qualifies technically, it may still need to satisfy direct transport or permitted transit requirements.

AIS treats this as a separate legal check rather than burying it inside the PSR logic.

## Why AIS Separates These Layers

AIS separates:

- product-specific rules
- general rules

because that is how trust is preserved in the decision logic.

If the system merged them into one opaque outcome, a user would not know:

- which product rule applied
- whether the product passed the specific legal test
- whether it later failed on a broader rule

By keeping them separate, AIS can tell the user exactly:

- which rule applied
- which pathway passed or failed
- whether a broader origin rule later blocked the claim
