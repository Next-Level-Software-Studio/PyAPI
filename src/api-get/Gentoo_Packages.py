import urllib.request
import json
import xml.etree.ElementTree as ET
from urllib.error import HTTPError

class Repository:
    """Classe responsável por gerenciar e descobrir Repositórios (Overlays)."""
    URL_REPOS = "https://api.gentoo.org/overlays/repositories.xml"
    HEADERS = {'User-Agent': 'PyAPI/1.0'}
    
    # Cache de classe para evitar downloads repetidos do XML
    _cache = None

    def __init__(self, xml_element):
        """Blueprint para estruturar dados obtidos do XML oficial."""
        name_node = xml_element.find("name")
        self.name = name_node.text.strip() if name_node is not None else "Unknown"
        
        desc_node = xml_element.find("description")
        self.description = desc_node.text.strip() if desc_node is not None else ""
        
        homepage_node = xml_element.find("homepage")
        self.homepage = homepage_node.text.strip() if homepage_node is not None else ""
        
        source_node = xml_element.find("source")
        self.sync_uri = source_node.text.strip() if source_node is not None else ""
        self.sync_type = source_node.get("type") if source_node is not None else ""
        
        owner_node = xml_element.find("owner")
        self.owner_email = ""
        self.owner_name = ""
        if owner_node is not None:
            email_node = owner_node.find("email")
            name_node = owner_node.find("name")
            self.owner_email = email_node.text.strip() if email_node is not None else ""
            self.owner_name = name_node.text.strip() if name_node is not None else ""

    def info(self, information=None):
        if information and hasattr(self, information):
            return getattr(self, information)
        return None

    @classmethod
    def _load_cache(cls):
        """Baixa o XML uma única vez e monta um dicionário de busca rápida O(1)."""
        if cls._cache is not None:
            return

        cls._cache = {}
        req = urllib.request.Request(cls.URL_REPOS, headers=cls.HEADERS)
        try:
            with urllib.request.urlopen(req) as resp:
                # Otimização: iterparse limpa a memória e processa em stream
                context = ET.iterparse(resp, events=("end",))
                for event, elem in context:
                    if elem.tag == "repo":
                        repo_obj = cls(elem)
                        # Indexa pelo nome em minúsculas para busca ultra rápida
                        cls._cache[repo_obj.name.lower()] = repo_obj
                        elem.clear() # Libera memória do elemento processado
        except Exception as e:
            print(f"❌ Erro ao descarregar repositórios: {e}")
            cls._cache = {}

    @classmethod
    def list_all(cls):
        """Retorna uma lista com todos os Repositories utilizando o cache."""
        cls._load_cache()
        return list(cls._cache.values())

    @classmethod
    def get(cls, target_name):
        """Busca instantânea O(1) por um repositório específico usando o cache."""
        cls._load_cache()
        return cls._cache.get(target_name.lower())


class Package:
    """Classe responsável por descobrir Pacotes."""
    HEADERS = {'User-Agent': 'PyAPI/1.0'}

    def __init__(self, category, name, file_list, source_repo):
        """Blueprint para estruturar os dados do pacote e extrair versões de forma eficiente."""
        self.category = category
        self.name = name
        self.source_repository = source_repo
        
        # Otimização com list comprehension direta e startswith/endswith rápidos
        prefix = f"{name}-"
        self.versions = [
            f["name"][len(prefix):-7] # Corta o prefixo e o '.ebuild' via slice (muito mais rápido que .replace)
            for f in file_list 
            if f["name"].endswith(".ebuild") and f["name"].startswith(prefix)
        ]

    def info(self, information):
        if information and hasattr(self, information):
            return getattr(self, information)
        return None

    @classmethod
    def get(cls, category, package_name, repository):
        """Busca o pacote na API do GitHub."""
        repo_lower = repository.lower()
        if repo_lower == "gentoo":
            url = f"https://api.github.com/repos/gentoo/gentoo/contents/{category}/{package_name}"
        else:
            # CORRIGIDO: de {repo} para {repository}
            url = f"https://api.github.com/repos/gentoo-mirror/{repository}/contents/{category}/{package_name}"
            
        req = urllib.request.Request(url, headers=cls.HEADERS)
        try:
            with urllib.request.urlopen(req) as resp:
                file_list = json.loads(resp.read().decode('utf-8'))
                return cls(category, package_name, file_list, source_repo=repository)
        except HTTPError as e:
            if e.code == 404:
                print(f"❌ O pacote '{category}/{package_name}' não existe no repositório '{repository}'.")
            else:
                print(f"❌ Erro de Rede na API do GitHub (Código: {e.code})")
            return None
        except Exception as e:
            print(f"❌ Erro inesperado: {e}")
            return None


if __name__ == "__main__":
    import time

    # Teste de Velocidade do Cache de Repositórios
    print("--- Teste de Velocidade ---")
    
    start = time.time()
    guru = Repository.get("guru")
    print(f"1ª Busca ('guru') levou: {time.time() - start:.4f} segundos (Baixou o XML)")
    
    start = time.time()
    steam = Repository.get("steam-overlay")
    print(f"2ª Busca ('steam-overlay') levou: {time.time() - start:.6f} segundos (Instântaneo via Cache)")
    
    if guru:
        print(f"\nHomepage do Guru: {guru.info('homepage')}")
        
    # Exemplo de uso do Package (Corrigido)
    # cpuid = Package.get("sys-apps", "cpuid", "gentoo")
    # if cpuid:
    #     print(f"Versões encontradas: {cpuid.versions}")