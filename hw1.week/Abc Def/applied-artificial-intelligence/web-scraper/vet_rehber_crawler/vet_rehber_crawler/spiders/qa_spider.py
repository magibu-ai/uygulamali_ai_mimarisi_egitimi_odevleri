import scrapy

class QASpider(scrapy.Spider):
    name = "vetrehberqa"
    start_urls = [ f"https://vetrehberi.com/soru-cevap/sorular/kedi/page/{i}/" for i in range(0,100)]
    handle_httpstatus_list = [404]  # There is 404 but there is body

    def parse(self, response):
        if not response.body:
            self.logger.warning(f"Dead link found: {response.url}")
            return
        yield from response.follow_all(css=".status-publish .bbp-topic-title > a", callback=self.parse_qa)

    def parse_qa(self, response):
        def extract_with_css():
            qa_data = []
            for data in response.css(".bbp-body .bbp-reply-content"):
                post_selector = data.css('p *::text')
                print(post_selector.getall())
                text_data = " ".join([item.get().strip() for item in post_selector if item.get().strip()])
                if len(text_data) > 0:
                    qa_data.append(text_data)
            return qa_data

        qa_data = extract_with_css()
        if len(qa_data) <= 1:
            yield None
        else:
            yield {
                "content": qa_data,
            }