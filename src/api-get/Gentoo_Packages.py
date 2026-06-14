import urllib.request, json, urllib.parse
import xml.etree.ElementTree as ET
from urllib.error import HTTPError


class Repository:
    URL_REPOS = "https://api.gentoo.org/overlays/repositories.xml"
    
    HEADERS = {'User-Agent': 'api-get'}
    
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
    """Class responsible for managing and discovering Packages via Gentoo's Official API."""
    
    HEADERS = {
        'User-Agent': 'api-get',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Encoding': 'gzip, deflate'
    }
    
    _package_cache = {}

    def __init__(self, pack_json):
        data = pack_json.get("package", pack_json)
        
        self.category = data.get("category", "Unknown")
        self.name = data.get("name", "Unknown")
        self.description = data.get("description", "")
        
        homepage_data = data.get("homepage", [])
        self.homepage = homepage_data[0] if isinstance(homepage_data, list) and homepage_data else ""
        
        self.versions = []
        self.stable_versions = []
        self.testing_versions = []
        
        ebuilds_list = data.get("ebuilds", [])
        for ebuild in ebuilds_list:
            version = ebuild.get("version")
            if version:
                self.versions.append(version)
                
                keywords = ebuild.get("keywords", [])
                is_stable = any(kw.get("status") == "stable" for kw in keywords)
                
                if is_stable:
                    self.stable_versions.append(version)
                else:
                    self.testing_versions.append(version)
        
        self.versions = list(dict.fromkeys(self.versions))
        self.stable_versions = list(dict.fromkeys(self.stable_versions))
        self.testing_versions = list(dict.fromkeys(self.testing_versions))

        self.use_flags = {
            flag.get("name"): flag.get("description")
            for flag in data.get("use_flags", [])
            if flag.get("name")
        }

    def info(self, information):
        return getattr(self, information, None) if information else None

    @classmethod
    def _fetch_json(cls, url):
        req = urllib.request.Request(url, headers=cls.HEADERS)
        with urllib.request.urlopen(req) as resp:
            if resp.info().get('Content-Encoding') == 'gzip':
                import gzip
                data_bytes = gzip.decompress(resp.read())
            else:
                data_bytes = resp.read()
            return json.loads(data_bytes.decode('utf-8'))

    @classmethod
    def get(cls, category, package_name):
        """Fetches a specific package by category and name (Uses Cache)."""
        cache_key = f"{category.lower()}/{package_name.lower()}"
        if cache_key in cls._package_cache:
            return cls._package_cache[cache_key]

        url = f"https://packages.gentoo.org/packages/{category}/{package_name}.json"
        try:
            pack_json = cls._fetch_json(url)
            package_obj = cls(pack_json)
            cls._package_cache[cache_key] = package_obj
            return package_obj
        except Exception:
            return None

    @classmethod
    def search(cls, package_name):
        """Global search: Uses Gentoo's search API and extracts the real package."""
        query = urllib.parse.quote(package_name.lower())
        url = f"https://packages.gentoo.org/search.json?q={query}"
        try:
            results = cls._fetch_json(url)
            
            packages_found = []
            if isinstance(results, dict):
                for key in ["packages", "results", "packages_found"]:
                    if key in results:
                        packages_found = results[key]
                        break
                if not packages_found:
                    packages_found = [results]
            elif isinstance(results, list):
                packages_found = results

            if packages_found and len(packages_found) > 0:
                first_item = packages_found[0]
                
                if isinstance(first_item, dict):
                    pkg_data = first_item.get("package", first_item)
                    category = pkg_data.get("category")
                    name = pkg_data.get("name")
                elif isinstance(first_item, str) and "/" in first_item:
                    category, name = first_item.split("/", 1)
                else:
                    category, name = None, None
                
                if category and name:
                    return cls.get(category, name)

            return cls.get("app-misc", package_name)

        except Exception:
            return cls.get("app-misc", package_name)

    @classmethod
    def list_by_category(cls, category):
        """Returns a list containing the names of all packages inside a category."""
        url = f"https://packages.gentoo.org/categories/{category}.json"
        try:
            category_json = cls._fetch_json(url)
            data = category_json.get("category", category_json)
            return [pkg.get("name") for pkg in data.get("packages", []) if pkg.get("name")]
        except Exception:
            return []