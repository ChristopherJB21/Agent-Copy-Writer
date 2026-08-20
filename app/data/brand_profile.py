"""Brand Voice Guide: store profile as a config file (not a table, per MVP decision).

Injected into the copywriter and reviewer prompts so the tone stays consistent with the brand.
"""

BRAND_PROFILE: dict = {
    "store_name": "Reswara Fashion",
    "tone": (
        "Casual, warm, energetic, everyday English that is not stiff but still polite. "
        "Avoid overly formal wording."
    ),
    "audience": "Young adults and professionals aged 20-35 looking for comfortable outfits for work or hanging out.",
    "primary_products": ["Shirts", "Tees", "Pants", "Dresses", "Outerwear"],
    "cta_rules": (
        "The CTA must be direct and channel-specific: video -> 'tap the yellow cart', "
        "feed -> 'tap the link in bio', broadcast -> 'click the link in chat / product link'."
    ),
    "hashtags": ["#OOTD", "#Fashion", "#LocalBrand", "#LinenShirt", "#ClearanceSale"],
    "product_link_placeholder": "[Product Link]",
    "promo_rule": (
        "Every promo/stock claim MUST come from the given data (stock, discount, rating, "
        "testimonial, order counts). Fabricating numbers is forbidden (anti-hallucination)."
    ),
    "forbidden": [
        "claiming promo numbers / stock figures that are not in the data",
        "claims like '-100%' or 'everything free' without data",
        "overclaiming fabric properties (e.g. 'never fades, forever') without evidence",
    ],
}
