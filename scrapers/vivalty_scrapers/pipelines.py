import json
from pathlib import Path

from itemadapter import ItemAdapter

from vivalty_scrapers.utils import item_to_dict


class JsonExportPipeline:
    """Write scraped items to data/scraped/<output_name>.json for Django import."""

    def __init__(self, output_path: str):
        self.output_path = Path(output_path)
        self.items: list[dict] = []

    @classmethod
    def from_crawler(cls, crawler):
        output = crawler.settings.get("VIVALTY_SCRAPER_OUTPUT")
        if not output:
            raise ValueError("VIVALTY_SCRAPER_OUTPUT must be set in Scrapy settings.")
        return cls(output)

    def open_spider(self, spider):
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self.items = []

    def close_spider(self, spider):
        payload = [item_to_dict(row) for row in self.items]
        self.output_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        spider.logger.info("Wrote %s listings to %s", len(payload), self.output_path)

    def process_item(self, item, spider):
        self.items.append(ItemAdapter(item).asdict())
        return item
