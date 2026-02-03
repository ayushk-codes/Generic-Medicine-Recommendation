class TrieNode:
    def __init__(self):
        self.children = {}
        self.is_end_of_word = False
        self.data = None 

class MedicineTrie:
    def __init__(self):
        self.root = TrieNode()

    def insert(self, word, medicine_data):
        node = self.root
        for char in word.lower():
            if char not in node.children:
                node.children[char] = TrieNode()
            node = node.children[char]
        node.is_end_of_word = True
        node.data = medicine_data

    def search_prefix(self, prefix):
        node = self.root
        for char in prefix.lower():
            if char not in node.children:
                return [] 
            node = node.children[char]
        
        # DFS to find all matches from this prefix
        results = []
        self._dfs(node, results)
        return results

    def _dfs(self, node, results):
        if len(results) >= 20: # Limit results to 20 for speed
            return
        if node.is_end_of_word:
            results.append(node.data)
        
        for char in node.children:
            self._dfs(node.children[char], results)