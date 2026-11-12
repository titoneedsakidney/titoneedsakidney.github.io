// Amazon Attribution tag addresses, one per outreach campaign and book (ASIN). A campaign or book with no entry keeps the plain Amazon address.
// Shape: window.TNK_ATTRIBUTION = { 'cmp-01': { ASIN: 'https://www.amazon.com/dp/ASIN?maas=...' }, 'site-default': { ... } };
// A tag identifies a campaign and a book, never a person. See research/outreach/governance/FIRST_CONTACT_LINK_TRACKING.md (Amazon Attribution).
window.TNK_ATTRIBUTION = window.TNK_ATTRIBUTION || {
  "cmp-01": {
    "B0DSXVL84P": "https://www.amazon.com/dp/B0DSXVL84P?maas=maas_adg_5D31B4BCCC27CF19E79BCF792D3DEFC7_afap_abs&ref_=aa_maas&tag=maas",
    "B0GCTHKNBR": "https://www.amazon.com/dp/B0GCTHKNBR?maas=maas_adg_3469BA63B560DA51A94D5A2FBABC52B0_afap_abs&ref_=aa_maas&tag=maas",
    "B0GCVN3YJW": "https://www.amazon.com/dp/B0GCVN3YJW?maas=maas_adg_39483BC14CA65C592BE781476D01B959_afap_abs&ref_=aa_maas&tag=maas",
    "B0DT1N3FFG": "https://www.amazon.com/dp/B0DT1N3FFG?maas=maas_adg_DFAF91F627DA52407AAF59D6F18D5DD9_afap_abs&ref_=aa_maas&tag=maas"
  },
  "site-default": {
    "B0DSXVL84P": "https://www.amazon.com/dp/B0DSXVL84P?maas=maas_adg_5BC77BAF5C0365233AF2671DEBD14A23_afap_abs&ref_=aa_maas&tag=maas",
    "B0DT1N3FFG": "https://www.amazon.com/dp/B0DT1N3FFG?maas=maas_adg_F84F7AA7029B37E01872692A1C13BAF8_afap_abs&ref_=aa_maas&tag=maas",
    "B0GCTHKNBR": "https://www.amazon.com/dp/B0GCTHKNBR?maas=maas_adg_C81B577C27DE62FDA70BE04FE14A72E7_afap_abs&ref_=aa_maas&tag=maas",
    "B0GCVN3YJW": "https://www.amazon.com/dp/B0GCVN3YJW?maas=maas_adg_22A87DEEF321AC007B1F3891842B0117_afap_abs&ref_=aa_maas&tag=maas"
  }
};
