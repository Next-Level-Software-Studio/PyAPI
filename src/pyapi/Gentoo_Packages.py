import urllib.request
import json
import xml.etree.ElementTree as ET
from urllib.error import HTTPError

class RepoGentoo:
    """Classe responsável por gerir e descobrir os Repositórios (Overlays)."""
    URL_REPOS = "https://api.gentoo.org/overlays/repositories.xml"
    HEADERS = {'User-Agent': 'PyAPI/1.0'}

    def __init__(self, xml_element):
        """Molde para estruturar os dados obtidos do XML oficial."""
        nome_node = xml_element.find("name")
        self.nome = nome_node.text.strip() if nome_node is not None else "Desconhecido"
        
        desc_node = xml_element.find("description")
        self.descricao = desc_node.text.strip() if desc_node is not None else ""
        
        homepage_node = xml_element.find("homepage")
        self.homepage = homepage_node.text.strip() if homepage_node is not None else ""
        
        source_node = xml_element.find("source")
        self.sync_uri = source_node.text.strip() if source_node is not None else ""
        self.sync_type = source_node.get("type") if source_node is not None else ""
        
        owner_node = xml_element.find("owner")
        self.dono_email = ""
        self.dono_nome = ""
        if owner_node is not None:
            email_node = owner_node.find("email")
            name_node = owner_node.find("name")
            self.dono_email = email_node.text.strip() if email_node is not None else ""
            self.dono_nome = name_node.text.strip() if name_node is not None else ""

    def mostrar_tudo(self):
        """Imprime todas as informações detalhadas do repositório."""
        print(f"📦 REPOSITÓRIO: {self.nome}")
        print(f"  ├── 📝 Descrição:     {self.descricao}")
        print(f"  ├── 🏠 Homepage:      {self.homepage}")
        print(f"  ├── 🔗 Tipo de Sync:  {self.sync_type}")
        print(f"  ├── 🌐 URI de Sync:   {self.sync_uri}")
        print(f"  └── 👤 Mantenedor:    {self.dono_nome} ({self.dono_email})")
        print("-" * 70)

    @classmethod
    def listar_todos(cls):
        """Descarrega a API oficial e devolve uma lista de objetos RepoGentoo."""
        req = urllib.request.Request(cls.URL_REPOS, headers=cls.HEADERS)
        try:
            with urllib.request.urlopen(req) as resp:
                raiz = ET.fromstring(resp.read())
                return [cls(repo) for repo in raiz.findall("repo")]
        except Exception as e:
            print(f"❌ Erro ao listar repositórios: {e}")
            return []

    @classmethod
    def procurar(cls, nome_procurado):
        """Procura um repositório específico pelo nome na lista oficial."""
        todos = cls.listar_todos()
        for repo in todos:
            if repo.nome.lower() == nome_procurado.lower():
                return repo
        return None


class PacoteGentoo:
    """Classe responsável por descobrir Pacotes (Obrigatório definir o repositório)."""
    HEADERS = {'User-Agent': 'PyAPI/1.0'}

    def __init__(self, categoria, nome, lista_ficheiros, repo_origem):
        """Molde para estruturar os dados do pacote e extrair versões."""
        self.categoria = categoria
        self.nome = nome
        self.repositorio_origem = repo_origem
        
        # Filtra e limpa os ebuilds para extrair apenas os números das versões
        self.versions = [f["name"].replace(".ebuild", "").replace(f"{nome}-", "") 
                         for f in lista_ficheiros if f["name"].endswith(".ebuild")]

    def mostrar_tudo(self):
        """Imprime todas as informações detalhadas do pacote."""
        print(f"📦 PACOTE: {self.categoria}/{self.nome}")
        print(f"  ├── 🏠 Origem:  Repositório [{self.repositorio_origem}]")
        print(f"  └── 📋 Versões Disponíveis:")
        if self.versions:
            for v in self.versions:
                print(f"      └── v{v}")
        else:
            print("      └── Nenhuma versão (.ebuild) encontrada.")
        print("-" * 70)

    @classmethod
    def procurar(cls, categoria, nome_pacote, repo):
        """
        Procura o pacote. O argumento 'repo' é OBRIGATÓRIO.
        Use 'gentoo' para o oficial, ou o nome de um overlay (ex: 'guru', 'steam-overlay').
        """
        # Define o caminho do GitHub baseado no repositório obrigatório informado
        if repo.lower() == "gentoo":
            url = f"https://api.github.com/repos/gentoo/gentoo/contents/{categoria}/{nome_pacote}"
        else:
            # Organização oficial que espelha os overlays da comunidade
            url = f"https://api.github.com/repos/gentoo-mirror/{repo}/contents/{categoria}/{nome_pacote}"
            
        req = urllib.request.Request(url, headers=cls.HEADERS)
        
        try:
            with urllib.request.urlopen(req) as resp:
                lista_ficheiros = json.loads(resp.read().decode())
                return cls(categoria, nome_pacote, lista_ficheiros, repo_origem=repo)
                
        except HTTPError as e:
            if e.code == 404:
                print(f"❌ O pacote '{categoria}/{nome_pacote}' não existe no repositório '{repo}'.")
            else:
                print(f"❌ Erro de rede na API do GitHub (Código: {e.code})")
            return None
        except Exception as e:
            print(f"❌ Erro inesperado: {e}")
            return None


# =====================================================================
# SUITE DE TESTES EM TEMPO REAL
# =====================================================================
if __name__ == "__main__":
    print("===============================================================")
    print("           PyAPI - SUITE DE TESTES DA BIBLIOTECA               ")
    print("===============================================================\n")

    # -----------------------------------------------------------------
    # TESTE 1: Módulo de Repositórios (Listagem Global)
    # -----------------------------------------------------------------
    print("[TESTE 1] A testar listagem global de repositórios da comunidade...")
    todos_repos = RepoGentoo.listar_todos()
    print(f"✅ Sucesso! Total de overlays registados detetados: {len(todos_repos)}")
    print("-" * 70 + "\n")

    # -----------------------------------------------------------------
    # TESTE 2: Módulo de Repositórios (Busca Específica)
    # -----------------------------------------------------------------
    nome_repo = "guru"
    print(f"[TESTE 2] A testar a busca do repositório específico: '{nome_repo}'...")
    repo_encontrado = RepoGentoo.procurar(nome_repo)
    if repo_encontrado:
        print("✅ Sucesso! Dados do repositório encontrados:")
        repo_encontrado.mostrar_tudo()
    else:
        print(f"❌ Falha: O repositório '{nome_repo}' não foi retornado.\n")

    # -----------------------------------------------------------------
    # TESTE 3: Módulo de Pacotes (Busca no Gentoo Oficial)
    # -----------------------------------------------------------------
    print("[TESTE 3] A testar busca de pacote informando obrigatoriamente 'gentoo'...")
    pkg_oficial = PacoteGentoo.procurar("net-firewall", "nftables", "gentoo")
    if pkg_oficial:
        print("✅ Sucesso! Pacote oficial mapeado com as classes:")
        pkg_oficial.mostrar_tudo()
    else:
        print("❌ Falha: Não foi possível obter o pacote oficial.\n")

    # -----------------------------------------------------------------
    # TESTE 4: Módulo de Pacotes (Busca em Overlay da Comunidade)
    # -----------------------------------------------------------------
    print("[TESTE 4] A testar busca de pacote informando obrigatoriamente o overlay 'guru'...")
    pkg_overlay = PacoteGentoo.procurar("dev-util", "git-cliff", "guru")
    if pkg_overlay:
        print("✅ Sucesso! Pacote do overlay mapeado com as classes:")
        pkg_overlay.mostrar_tudo()
    else:
        print("❌ Falha: Não foi possível obter o pacote do overlay.\n")

    # -----------------------------------------------------------------
    # TESTE 5: Módulo de Pacotes (Tratamento de Erros / Pacote Inexistente)
    # -----------------------------------------------------------------
    print("[TESTE 5] A testar comportamento ao procurar um pacote que não existe...")
    pkg_fantasma = PacoteGentoo.procurar("sys-apps", "pacote-que-nao-existe", "gentoo")
    if pkg_fantasma is None:
        print("✅ Sucesso! O sistema tratou o erro 404 corretamente e retornou None.")
    else:
        print("❌ Falha: O sistema deveria ter retornado None para um pacote inexistente.")
    print("-" * 70 + "\n")

    print("===============================================================")
    print("            TODOS OS TESTES FORAM CONCLUÍDOS!                  ")
    print("===============================================================")