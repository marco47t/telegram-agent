import urllib.request
import urllib.parse
import json
from abc import ABC, abstractmethod

class WebSearchProvider(ABC):
    @abstractmethod
    def perform_search(self, query: str) -> list[dict]:
        """
        Takes a query string and returns a list of dictionaries with keys:
        - 'title': Title of the search result
        - 'url': URL of the result
        - 'snippet': A short snippet or description
        """
        pass

class DuckDuckGoSearchProvider(WebSearchProvider):
    def perform_search(self, query: str) -> list[dict]:
        """
        Uses DuckDuckGo's Instant Answer API.
        Note: The free API is limited and often only returns one abstract.
        For production, you could replace this provider with one that hits
        a paid API (e.g., Brave Search API, Google Custom Search) and inject
        an API key here.
        """
        # Note: If we had an API key for a paid provider, it would be passed in via os.environ here.
        # e.g. api_key = os.environ.get("BRAVE_SEARCH_API_KEY")

        url = f"https://api.duckduckgo.com/?q={urllib.parse.quote(query)}&format=json"

        req = urllib.request.Request(
            url,
            headers={'User-Agent': 'TelegramBotAgent/1.0'}
        )

        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode('utf-8'))

                    results = []
                    # DuckDuckGo's instant answer might provide an abstract
                    if data.get('AbstractText'):
                        results.append({
                            'title': data.get('Heading', 'DuckDuckGo Instant Answer'),
                            'url': data.get('AbstractURL', ''),
                            'snippet': data.get('AbstractText', '')
                        })

                    # They also provide related topics
                    if data.get('RelatedTopics'):
                        for topic in data['RelatedTopics']:
                            if 'Text' in topic and 'FirstURL' in topic:
                                results.append({
                                    'title': topic.get('Text', '').split(' - ')[0] if ' - ' in topic.get('Text', '') else 'Related Topic',
                                    'url': topic.get('FirstURL', ''),
                                    'snippet': topic.get('Text', '')
                                })

                    return results[:5]  # limit to top 5 results
        except Exception as e:
            # Fall through to return empty list on error
            pass

        return []

# Expose a default instance and wrapper function for easy use
_default_provider = DuckDuckGoSearchProvider()

def perform_search(query: str) -> list[dict]:
    return _default_provider.perform_search(query)
