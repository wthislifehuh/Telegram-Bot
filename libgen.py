import time
import random
import re
import math
import sys
import urllib.parse
import grab
import weblib


class MissingMirrorsError(Exception):
    """Raised when there are no mirrors available."""
    pass


class MirrorsNotResolvingError(Exception):
    """Raised when none of the mirrors are resolving."""
    pass


class LibgenAPI:
    """Library Genesis API for searching books."""

    def __init__(self, mirrors=None):
        self.grabber = grab.Grab()
        self.mirrors = mirrors if isinstance(mirrors, list) else [mirrors] if mirrors else []
        self.__selected_mirror = None

    def set_mirrors(self, mirrors):
        """Set the mirrors list."""
        self.mirrors = mirrors if isinstance(mirrors, list) else [mirrors]

    def __choose_mirror(self):
        if self.__selected_mirror:
            return
        
        if not self.mirrors:
            raise MissingMirrorsError("No mirrors available!")
        
        for mirror in self.mirrors:
            try:
                self.grabber.go(mirror)
                self.__selected_mirror = mirror
                return
            except grab.GrabError:
                continue
        
        raise MirrorsNotResolvingError("None of the mirrors are resolving. Check your connection!")

    def __parse_books(self):
        """Parses book details from the search results page."""
        books = []
        fields = [
            "author", "series_title_edition_and_isbn", "publisher", "year",
            "pages", "language", "size", "extension", "mirror", "mirror", "mirror", "mirror"
        ]

        book_template = lambda: {
            "author": None, "series": None, "title": None, "edition": None, "isbn": None,
            "publisher": None, "year": None, "pages": None, "language": None,
            "size": None, "extension": None, "mirrors": []
        }

        book = book_template()
        i = 0

        for result in self.grabber.doc.select('//body/table[3]/tr[position()>1]/td[position()>1 and position()<14]'):
            if i >= len(fields):
                books.append(book)
                book = book_template()
                i = 0

            field = fields[i]
            
            if field == "mirror":
                mirror = result.select("a/@href")
                if mirror:
                    book["mirrors"].append(mirror.text().replace("../", f"{self.__selected_mirror}/"))
            elif field == "series_title_edition_and_isbn":
                try:
                    book["title"] = result.select("a/text()").text()
                    green_texts = result.select("a/font")
                    
                    isbn_pattern = re.compile(r"ISBN[-]*(1[03])*[ ]*(: )?[0-9Xx][- ]*(13|10)")
                    edition_pattern = re.compile(r'\[[0-9] ed\.\]')
                    
                    for text in green_texts:
                        text_content = text.text()
                        if isbn_pattern.search(text_content):
                            book["isbn"] = [match.group(0) for match in isbn_pattern.finditer(text_content)]
                        elif edition_pattern.search(text_content):
                            book["edition"] = text_content
                        else:
                            book["series"] = text_content
                except weblib.error.DataNotFound:
                    book["title"] = result.text()
            else:
                book[field] = result.text()
            
            i += 1

        books.append(book)
        return books

    def search(self, search_term, column="title", number_results=5):
        """Search for books in Library Genesis."""
        self.__choose_mirror()
        
        request_params = {"req": search_term, "column": column}
        url = f"{self.__selected_mirror}/search.php?{urllib.parse.urlencode(request_params)}"
        self.grabber.go(url)

        search_results = []
        match = re.search(r'([0-9]+) (books|files)', self.grabber.doc.select("/html/body/table[2]/tr/td[1]/font").text())
        total_books = int(match.group(1)) if match else 0
        
        pages_to_load = min(math.ceil(number_results / 25), math.ceil(total_books / 25))

        for page in range(1, pages_to_load + 1):
            if len(search_results) >= number_results:
                break

            request_params["page"] = page
            url = f"{self.__selected_mirror}/search.php?{urllib.parse.urlencode(request_params)}"
            self.grabber.go(url)
            search_results.extend(self.__parse_books())
            
            if page != pages_to_load:
                time.sleep(random.uniform(0.25, 1.0))  # Random delay to prevent blocking
        
        return search_results[:number_results]
