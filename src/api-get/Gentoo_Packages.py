import urllib.request
import json
import xml.etree.ElementTree as ET
from urllib.error import HTTPError

class Repository:
    """Classe responsável por gerenciar e descobrir Repositórios (Overlays)."""
    URL_REPOS = "https://api.gentoo.org/overlays/repositories.xml"
    HEADERS = {'User-Agent': 'api-get/1.0'}
    
    _cache = None

    def __init__(self, xml_element):
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
        return getattr(self, information, None) if information else None

    @classmethod
    def _load_cache(cls):
        if cls._cache is not None:
            return

        cls._cache = {}
        req = urllib.request.Request(cls.URL_REPOS, headers=cls.HEADERS)
        try:
            with urllib.request.urlopen(req) as resp:
                context = ET.iterparse(resp, events=("end",))
                for event, elem in context:
                    if elem.tag == "repo":
                        repo_obj = cls(elem)
                        cls._cache[repo_obj.name.lower()] = repo_obj
                        elem.clear() 
        except Exception:
            cls._cache = None 

    @classmethod
    def list_all(cls):
        cls._load_cache()
        return list(cls._cache.values()) if cls._cache else []

    @classmethod
    def get(cls, target_name):
        cls._load_cache()
        return cls._cache.get(target_name.lower()) if cls._cache else None


class Package:
    """Classe responsável por descobrir Pacotes com cache local ultra rápido."""
    HEADERS = {'User-Agent': 'api-get/1.0', 'Accept-Encoding': 'gzip'}
    
    # Cache de pacotes para buscas repetidas instantâneas
    _package_cache = {}

    def __init__(self, pack_json):
        # A API do Gentoo entrega os metadados do pacote dentro da chave principal "package"
        data = pack_json.get("package", pack_json)
        
        self.category = data.get("category", "Unknown")
        self.name = data.get("name", "Unknown")
        self.description = data.get("description", "")
        
        homepage_data = data.get("homepage", [])
        self.homepage = homepage_data[0] if isinstance(homepage_data, list) and homepage_data else ""
        
        # Na API oficial, as versões ficam dentro da lista de "ebuilds"
        ebuilds_list = data.get("ebuilds", [])
        
        # Extrai a string da versão de cada ebuild usando list comprehension de alta performance
        # Usamos dict.fromkeys() para remover duplicatas de forma rápida e limpa
        self.versions = list(dict.fromkeys([
            ebuild.get("version") 
            for ebuild in ebuilds_list 
            if ebuild.get("version")
        ]))

    def info(self, information):
        return getattr(self, information, None) if information else None

    @classmethod
    def get(cls, category, package_name):
        """Busca o pacote na API do Gentoo ou retorna do Cache se já foi buscado."""
        cache_key = f"{category.lower()}/{package_name.lower()}"
        
        if cache_key in cls._package_cache:
            return cls._package_cache[cache_key]

        url = f"https://packages.gentoo.org/packages/{category}/{package_name}.json"
        req = urllib.request.Request(url, headers=cls.HEADERS)
        
        try:
            with urllib.request.urlopen(req) as resp:
                if resp.info().get('Content-Encoding') == 'gzip':
                    import gzip
                    data = gzip.decompress(resp.read())
                else:
                    data = resp.read()
                    
                pack_json = json.loads(data.decode('utf-8'))
                
                package_obj = cls(pack_json)
                cls._package_cache[cache_key] = package_obj
                return package_obj
                
        except HTTPError:
            return None
        except Exception:
            return None


if __name__ == "__main__":
    import time

    print("--- Teste de Velocidade de Pacotes (Com Cache) ---")
    
    # 1ª vez: Vai na Web buscar os dados da API oficial
    start = time.time()
    pkg1 = Package.get("app-shells", "fish")
    print(f"1ª Busca (Web) levou: {time.time() - start:.4f} segundos")
    
    # 2ª vez: Busca local instantânea O(1)
    start = time.time()
    pkg2 = Package.get("app-shells", "fish")
    print(f"2ª Busca (Cache) levou: {time.time() - start:.6f} segundos (Instantâneo)")

    if pkg1:
        print(f"\nPacote: {pkg1.category}/{pkg1.name}")
        print(f"Descrição: {pkg1.description}")
        print(f"Versões: {pkg1.versions}")