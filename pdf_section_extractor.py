"""
Class to extract sections from a PDF file and save them to a JSON file.
"""
import os
import re
import string
import json
from typing import Dict, List, Tuple, Pattern
import fitz

class PDFSectionExtractor:
    """
    Class takes a PDF file path and extracts the sections from the PDF file.
    
    ```python
    extractor = PDFSectionExtractor("path/to/pdf")
    extractor.extract_sections_to_json("path/to/json")
    ```
    
    """
    def __init__(self, pdf_path: str):
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"File {pdf_path} not found")
        self.pdf_path = pdf_path
        self.doc = fitz.open(self.pdf_path)

    def clean_text(self, text: str) -> str:
        """Clean text by removing punctuation, newlines, and extra spaces.
        Args:
            text (str): text to be cleaned
        Returns:
            str: cleaned text
        """
        # make a string of all punctuation characters with some extra character
        characters_to_replace = string.punctuation + '—’'
        # replace punctuation with spaces and remove extra spaces using translate
        text = text.translate(str.maketrans(characters_to_replace,
                                            ' ' * len(characters_to_replace)))
        # replacea any withespaces with a single space , lower case the text and strip it
        return re.sub(r'\s+', ' ', text.lower()).strip()

    @staticmethod
    def is_chapter_line(line: str) -> bool:
        """Check if a line is a chapter heading.
        Args:
            line (str): line from the table of contents
        Returns:
            bool: whether the line is a chapter heading or not
        """
        return "CHAPTER" in line

    @staticmethod
    def is_section_line(line: str) -> bool:
        """Check if a line is a section heading.
        Args:
            line (str): line from the table of contents
        Returns:
            bool: whether the line is a section heading or not
        """

        return bool(re.match(r"^\d+\.\s+[A-Za-z].*", line.strip()))

    def process_toc_line(
        self,
        line: str,
        current_chapter: str,
        chapters_sections: Dict) -> str:
        """Process a line from the table of contents.
        Args:
            line (str): the line from the table of contents
            current_chapter (str): the current chapter for example CHAPTER I, CHAPTER II etc
            chapters_sections (dict): dictionary to store the chapters and sections
        Returns:
            str: the current chapter
        """
        if self.is_chapter_line(line):
            current_chapter = line.strip()
            chapters_sections[current_chapter] = []
        elif self.is_section_line(line):
            section = re.match(r"^\d+\.\s+[A-Za-z].*", line.strip()).group()
            section_title = self.clean_text(section)
            chapters_sections[current_chapter].append(section_title)
        return current_chapter

    def extract_table_of_contents(self) -> Tuple[Dict[str, List[str]], int]:
        """Extract the table of contents from the document.
        Returns:
            Tuple: a tuple containing a dictionary of chapters and sections
            and the last page
        """
        chapters_sections = {}
        current_chapter = ""
        toc_found = False
        last_page = 0

        for page in self.doc:
            text = page.get_text("text")
            first_page = False
            last_page = page.number

            if "ARRANGEMENT OF SECTIONS" in text:
                toc_found = True
                first_page = True
                text = text.split("ARRANGEMENT OF SECTIONS")[1]

            if toc_found:
                if self.doc.metadata['title'] in text and not first_page:
                    break
                for line in text.split('\n'):
                    current_chapter = self.process_toc_line(line, current_chapter,
                                                            chapters_sections)
        return chapters_sections, last_page

    def compile_section_pattern(self, section: str) -> Pattern:
        """Compile a regex pattern for a section.
        Args:
            section (str): section title
        Returns:
            re.Pattern: regex pattern for the section
        """
        words = section.split()
        # there are some sections that end with 's' in section titles but not in the text
        pluralized_words = [f"{word}s?" if not word.endswith('s') else f"{word}?" for word in words]
        return re.compile(r'\s'.join(pluralized_words) + r"(.*?)(?=\f|\Z)", re.DOTALL)

    def extract_section_content(self, start_page: int, sections: List) -> Dict:
        """Extract the content of the sections from the document.
        Args:
            start_page (int): the page to start extracting the sections from
            sections (list): list of sections to extract
        Returns:
            dict: dictionary containing the sections and their content
        """
        formatted_data = {}
        section_patterns = [self.compile_section_pattern(section) for section in sections]
        current_section_index = 0
        current_section_text = ""

        # start from the page after the table of contents
        for page_num in range(start_page, len(self.doc)):
            page = self.doc[page_num]
            text = self.clean_text(page.get_text("text"))
            page_processed = False
            
            while current_section_index < len(sections) - 1 and not page_processed:
                next_section_pattern = section_patterns[current_section_index + 1]
                next_match = next_section_pattern.search(text)

                if next_match:
                    # Process the current section up to the start of the next section
                    current_section_text += text[:next_match.start()].strip()
                    formatted_data[sections[current_section_index]] = current_section_text

                    # Prepare for the next section
                    current_section_index += 1
                    current_section_text = ""
                    text = text[next_match.start():]  # Update text to start from next section
                else:
                    page_processed = True
                    current_section_text += text

        # Add the last section to the formatted data
        formatted_data[sections[current_section_index]] = text

        return formatted_data

    def save_data_to_json(self, data: dict, file_path: str)->None:
        """Save data to a JSON file.
        Args:
            data (dict): the data to be saved
            file_path (str): the path to save the data to
        """
        with open(file_path, 'w', encoding='utf-8') as file:
            json.dump(data, file, indent=4)

    def extract_sections_to_json(self, json_path: str)->None:
        """Main function to extract sections from a PDF and save them to a JSON file.\n
        Args:
            json_path (str): the path to save the data to
        """
        try:
            chapters_sections, end_page = self.extract_table_of_contents()
            sections = [sec for secs in chapters_sections.values() for sec in secs]
            formatted_data = self.extract_section_content(end_page, sections)
            self.save_data_to_json(formatted_data, json_path)
        except (FileNotFoundError, IOError, PermissionError) as file_error:
            print(f"File error occurred: {file_error}")
        except re.error as regex_error:
            print(f"Regex error occurred: {regex_error}")
        except (ValueError, IndexError) as processing_error:
            print(f"Data processing error occurred: {processing_error}")
        except Exception as error:
            print(f"Unknown error occurred: {error}")

if __name__ == "__main__":
    extractor = PDFSectionExtractor("data/crpc.pdf")
    extractor.extract_sections_to_json("data/crpc.json")
