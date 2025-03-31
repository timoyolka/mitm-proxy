import re

class TrieNode:
    def __init__(self):
        self.children = {}
        self.is_end_of_rule = False  # Marks the end of a rule


class Trie:
    def __init__(self):
        self.root = TrieNode()

    def insert(self, rule: str):
        """
        Insert a rule into the Trie.
        Rules can include wildcards (*) for partial matches.
        """
        node = self.root
        parts = rule.split("*")  # Split by wildcard
        for part in parts:
            if not part:
                continue
            if "*" not in part:  # Exact part
                for char in part:
                    if char not in node.children:
                        node.children[char] = TrieNode()
                    node = node.children[char]
            else:  # Wildcard part
                node.children["*"] = TrieNode()  # Add a wildcard node
                node = node.children["*"]
        node.is_end_of_rule = True  # Mark the end of the rule

    def search(self, url: str) -> bool:
        """
        Search for a URL in the Trie.
        Returns True if the URL matches any rule in the Trie.
        """
        def _search(node, url, index):
            if index == len(url):
                return node.is_end_of_rule

            char = url[index]

            # Check exact match
            if char in node.children:
                if _search(node.children[char], url, index + 1):
                    return True

            # Check wildcard match
            if "*" in node.children:
                for i in range(index, len(url) + 1):  # Try all possible wildcard lengths
                    if _search(node.children["*"], url, i):
                        return True

            return node.is_end_of_rule

        return _search(self.root, url, 0)
        

class EasyListParser:
    def __init__(self):
        self.trie = Trie()  # Use the Trie for static and wildcard rules
        self.regex_rules = []  # For regex-based rules

    def parse_easylist(self, easylist_content: str):
        """
        Parse the EasyList content and populate the Trie and regex rules.
        """
        for line in easylist_content.splitlines():
            line = line.strip()
            if not line or line.startswith("!"):  # Skip comments and empty lines
                continue

            if line.startswith("||") and "*" not in line and "/" not in line:
                # Static rule (e.g., ||example.com)
                domain = line[2:].split("^")[0]
                self.trie.insert(domain)
            elif "*" in line or "/" in line:
                # Wildcard or complex rule (e.g., ||example.com/*banner*)
                self.trie.insert(line)
            elif line.startswith("/") and line.endswith("/"):
                # Regex rule (e.g., /^https?:\/\/example\.com\/ads/)
                regex = re.compile(line[1:-1])
                self.regex_rules.append(regex)

    def match_url(self, url: str) -> bool:
        """
        Match a URL against the Trie and regex rules.
        Returns True if the URL matches any ad-blocking rule.
        """
        # Check the Trie for static and wildcard matches
        if self.trie.search(url):
            return True

        # Check regex rules
        for regex in self.regex_rules:
            if regex.match(url):
                return True

        return False