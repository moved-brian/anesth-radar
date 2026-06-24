from .tsa    import scrape as scrape_tsa
from .pain   import scrape as scrape_pain
from .rapm   import scrape as scrape_rapm
from .tscva  import scrape as scrape_tscva
from .tweras import scrape as scrape_tweras
from .tsccm  import scrape as scrape_tsccm

ALL_SCRAPERS = {
    "TSA":    scrape_tsa,
    "PAIN":   scrape_pain,
    "RAPM":   scrape_rapm,
    "TSCVA":  scrape_tscva,
    "TWERAS": scrape_tweras,
    "TSCCM":  scrape_tsccm,
}
