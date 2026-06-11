#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <curl/curl.h>
#include <libxml/parser.h>
#include <libxml/tree.h>
#include <cjson/cJSON.h>

#define URL_REPOS "https://api.gentoo.org/overlays/repositories.xml"
#define USER_AGENT "PyAPI/1.0"

// Estrutura para armazenar a resposta da requisição HTTP na memória
struct Memoria {
    char *resposta;
    size_t tamanho;
};

// Estrutura equivalente à classe RepoGentoo
typedef struct {
    char nome[100];
    char descricao[500];
    char homepage[256];
    char sync_uri[256];
    char sync_type[50];
    char dono_email[100];
    char dono_nome[100];
} RepoGentoo;

// Estrutura equivalente à classe PacoteGentoo
typedef struct {
    char categoria[100];
    char nome[100];
    char repositorio_origem[100];
    char versoes[50][50]; // Suporta até 50 versões por pacote
    int total_versoes;
} PacoteGentoo;

// Função auxiliar do cURL para escrever os dados recebidos na memória
static size_t EscreverMemoria(void *conteudo, size_t tamanho, size_t nmemb, void *usuario) {
    size_t tamanho_real = tamanho * nmemb;
    struct Memoria *mem = (struct Memoria *)usuario;

    char *ptr = realloc(mem->resposta, mem->tamanho + tamanho_real + 1);
    if(ptr == NULL) return 0; // Fora de memória

    mem->resposta = ptr;
    memcpy(&(mem->resposta[mem->tamanho]), conteudo, tamanho_real);
    mem->tamanho += tamanho_real;
    mem->resposta[mem->tamanho] = 0;

    return tamanho_real;
}

// Função para fazer requisições HTTP GET utilizando libcurl
char* fazer_requisicao(const char* url, long *codigo_http) {
    CURL *curl;
    CURLcode res;
    struct Memoria chunk = {NULL, 0};

    curl = curl_easy_init();
    if (!curl) return NULL;

    struct curl_slist *headers = NULL;
    headers = curl_slist_append(headers, "User-Agent: " USER_AGENT);

    curl_easy_setopt(curl, CURLOPT_URL, url);
    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, EscreverMemoria);
    curl_easy_setopt(curl, CURLOPT_WRITEDATA, (void *)&chunk);
    curl_easy_setopt(curl, CURLOPT_HTTPHEADER, headers);
    curl_easy_setopt(curl, CURLOPT_FOLLOWLOCATION, 1L);

    res = curl_easy_perform(curl);
    if(res != CURLE_OK) {
        if (chunk.resposta) free(chunk.resposta);
        chunk.resposta = NULL;
    } else {
        curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, codigo_http);
    }

    curl_slist_free_all(headers);
    curl_easy_cleanup(curl);
    return chunk.resposta;
}

// Helper para extrair texto de nós XML com segurança
void extrair_texto_xml(xmlNodePtr no, const char* nome_campo, char* destino, size_t max_len) {
    xmlNodePtr atual = no->children;
    while (atual != NULL) {
        if (strcmp((const char*)atual->name, nome_campo) == 0) {
            xmlChar* conteudo = xmlNodeGetContent(atual);
            if (conteudo) {
                snprintf(destino, max_len, "%s", (const char*)conteudo);
                xmlFree(conteudo);
                return;
            }
        }
        atual = atual->next;
    }
    strcpy(destino, "");
}

// Função para mapear um nó <repo> para a struct RepoGentoo
void preencher_repo(xmlNodePtr no, RepoGentoo *repo) {
    extrair_texto_xml(no, "name", repo->nome, sizeof(repo->nome));
    extrair_texto_xml(no, "description", repo->descricao, sizeof(repo->descricao));
    extrair_texto_xml(no, "homepage", repo->homepage, sizeof(repo->homepage));
    
    // Procura o nó source e extrai o atributo type e o texto interno
    xmlNodePtr atual = no->children;
    while (atual != NULL) {
        if (strcmp((const char*)atual->name, "source") == 0) {
            xmlChar* tipo = xmlGetProp(atual, (const xmlChar*)"type");
            if (tipo) {
                snprintf(repo->sync_type, sizeof(repo->sync_type), "%s", (const char*)tipo);
                xmlFree(tipo);
            }
            xmlChar* conteudo = xmlNodeGetContent(atual);
            if (conteudo) {
                snprintf(repo->sync_uri, sizeof(repo->sync_uri), "%s", (const char*)conteudo);
                xmlFree(conteudo);
            }
        }
        if (strcmp((const char*)atual->name, "owner") == 0) {
            extrair_texto_xml(atual, "email", repo->dono_email, sizeof(repo->dono_email));
            extrair_texto_xml(atual, "name", repo->dono_nome, sizeof(repo->dono_nome));
        }
        atual = atual->next;
    }
}

// Métodos de exibição e controle
void mostrar_tudo_repo(RepoGentoo *repo) {
    printf("📦 REPOSITÓRIO: %s\n", repo->nome);
    printf("  ├── 📝 Descrição:     %s\n", repo->descricao);
    printf("  ├── 🏠 Homepage:      %s\n", repo->homepage);
    printf("  ├── 🔗 Tipo de Sync:  %s\n", repo->sync_type);
    printf("  ├── 🌐 URI de Sync:   %s\n", repo->sync_uri);
    printf("  └── 👤 Mantenedor:    %s (%s)\n", repo->dono_nome, repo->dono_email);
    printf("----------------------------------------------------------------------\n");
}

void mostrar_tudo_pacote(PacoteGentoo *pkg) {
    printf("📦 PACOTE: %s/%s\n", pkg->categoria, pkg->nome);
    printf("  ├── 🏠 Origem:  Repositório [%s]\n", pkg->repositorio_origem);
    printf("  └── 📋 Versões Disponíveis:\n");
    if (pkg->total_versoes > 0) {
        for (int i = 0; i < pkg->total_versoes; i++) {
            printf("      └── v%s\n", pkg->versoes[i]);
        }
    } else {
        printf("      └── Nenhuma versão (.ebuild) encontrada.\n");
    }
    printf("----------------------------------------------------------------------\n");
}

// Descarrega o XML e devolve um array dinâmico de RepoGentoo
RepoGentoo* listar_todos_repos(int *total_repos) {
    long codigo_http = 0;
    char *xml_conteudo = fazer_requisicao(URL_REPOS, &codigo_http);
    *total_repos = 0;

    if (!xml_conteudo) {
        printf("❌ Erro ao listar repositórios: Falha na rede.\n");
        return NULL;
    }

    xmlDocPtr doc = xmlReadMemory(xml_conteudo, strlen(xml_conteudo), "noname.xml", NULL, 0);
    free(xml_conteudo);
    if (!doc) {
        printf("❌ Erro ao listar repositórios: Falha no parsing do XML.\n");
        return NULL;
    }

    xmlNodePtr raiz = xmlDocGetRootElement(doc);
    xmlNodePtr no_atual = raiz->children;

    // Conta quantos repositórios existem primeiro
    int capacidade = 0;
    while (no_atual != NULL) {
        if (strcmp((const char*)no_atual->name, "repo") == 0) capacidade++;
        no_atual = no_atual->next;
    }

    RepoGentoo *lista = malloc(sizeof(RepoGentoo) * capacidade);
    no_atual = raiz->children;
    int idx = 0;

    while (no_atual != NULL) {
        if (strcmp((const char*)no_atual->name, "repo") == 0) {
            preencher_repo(no_atual, &lista[idx]);
            idx++;
        }
        no_atual = no_atual->next;
    }

    *total_repos = idx;
    xmlFreeDoc(doc);
    return lista;
}

// Procura um repositório por nome na lista
RepoGentoo* procurar_repo(const char* nome_procurado) {
    int total = 0;
    RepoGentoo *todos = listar_todos_repos(&total);
    if (!todos) return NULL;

    RepoGentoo *resultado = NULL;
    for (int i = 0; i < total; i++) {
        // Comparação case-insensitive simples (strcasecmp do POSIX ou strcmpi)
#ifdef _WIN32
        if (strcmpi(todos[i].nome, nome_procurado) == 0) {
#else
        if (strcasecmp(todos[i].nome, nome_procurado) == 0) {
#endif
            resultado = malloc(sizeof(RepoGentoo));
            memcpy(resultado, &todos[i], sizeof(RepoGentoo));
            break;
        }
    }
    free(todos);
    return resultado;
}

// Procura e analisa pacotes consumindo o JSON da API do GitHub
PacoteGentoo* procurar_pacote(const char* categoria, const char* nome_pacote, const char* repo) {
    char url[512];
    long codigo_http = 0;

#ifdef _WIN32
    if (strcmpi(repo, "gentoo") == 0) {
#else
    if (strcasecmp(repo, "gentoo") == 0) {
#endif
        snprintf(url, sizeof(url), "https://api.github.com/repos/gentoo/gentoo/contents/%s/%s", categoria, nome_pacote);
    } else {
        snprintf(url, sizeof(url), "https://api.github.com/repos/gentoo-mirror/%s/contents/%s/%s", repo, categoria, nome_pacote);
    }

    char *json_conteudo = fazer_requisicao(url, &codigo_http);

    if (codigo_http == 404) {
        printf("❌ O pacote '%s/%s' não existe no repositório '%s'.\n", categoria, nome_pacote, repo);
        if (json_conteudo) free(json_conteudo);
        return NULL;
    } else if (codigo_http != 200 || !json_conteudo) {
        printf("❌ Erro de rede ou inesperado na API do GitHub (Código: %ld)\n", codigo_http);
        if (json_conteudo) free(json_conteudo);
        return NULL;
    }

    cJSON *raiz_json = cJSON_Parse(json_conteudo);
    free(json_conteudo);
    if (!raiz_json) return NULL;

    PacoteGentoo *pkg = malloc(sizeof(PacoteGentoo));
    snprintf(pkg->categoria, sizeof(pkg->categoria), "%s", categoria);
    snprintf(pkg->nome, sizeof(pkg->nome), "%s", nome_pacote);
    snprintf(pkg->repositorio_origem, sizeof(pkg->repositorio_origem), "%s", repo);
    pkg->total_versoes = 0;

    if (cJSON_IsArray(raiz_json)) {
        int tam_array = cJSON_GetArraySize(raiz_json);
        char sufixo_ebuild[50];
        snprintf(sufixo_ebuild, sizeof(sufixo_ebuild), "%s-", nome_pacote);

        for (int i = 0; i < tam_array && pkg->total_versoes < 50; i++) {
            cJSON *item = cJSON_GetArrayItem(raiz_json, i);
            cJSON *nome_ficheiro = cJSON_GetObjectItemCaseSensitive(item, "name");

            if (cJSON_IsString(nome_ficheiro) && nome_ficheiro->valuestring != NULL) {
                char *nome_f = nome_ficheiro->valuestring;
                size_t len_f = strlen(nome_f);
                
                // Filtro equivalente ao .endswith(".ebuild")
                if (len_f > 7 && strcmp(nome_f + len_f - 7, ".ebuild") == 0) {
                    char versao_limpa[64];
                    snprintf(versao_limpa, sizeof(versao_limpa), "%s", nome_f);
                    
                    // Remove o ".ebuild" no final
                    versao_limpa[strlen(versao_limpa) - 7] = '\0';
                    
                    // Remove o prefixo "nome_do_pacote-"
                    char *inicio_versao = strstr(versao_limpa, sufixo_ebuild);
                    if (inicio_versao == versao_limpa) {
                        inicio_versao += strlen(sufixo_ebuild);
                        snprintf(pkg->versoes[pkg->total_versoes], 50, "%s", inicio_versao);
                        pkg->total_versoes++;
                    }
                }
            }
        }
    }

    cJSON_Delete(raiz_json);
    return pkg;
}

// SUITE DE TESTES
int main() {
    // Inicialização global da biblioteca curl e xml
    curl_global_init(CURL_GLOBAL_ALL);
    LIBXML_TEST_VERSION

    printf("===============================================================\n");
    printf("           PyAPI - SUITE DE TESTES DA BIBLIOTECA (C VERSION)  \n");
    printf("===============================================================\n\n");

    // -----------------------------------------------------------------
    // TESTE 1: Módulo de Repositórios (Listagem Global)
    // -----------------------------------------------------------------
    printf("[TESTE 1] A testar listagem global de repositórios da comunidade...\n");
    int total_repos = 0;
    RepoGentoo *todos_repos = listar_todos_repos(&total_repos);
    if (todos_repos) {
        printf("✅ Sucesso! Total de overlays registados detetados: %d\n", total_repos);
        free(todos_repos);
    }
    printf("----------------------------------------------------------------------\n\n");

    // -----------------------------------------------------------------
    // TESTE 2: Módulo de Repositórios (Busca Específica)
    // -----------------------------------------------------------------
    const char* nome_repo = "guru";
    printf("[TESTE 2] A testar a busca do repositório específico: '%s'...\n", nome_repo);
    RepoGentoo *repo_encontrado = procurar_repo(nome_repo);
    if (repo_encontrado) {
        printf("✅ Sucesso! Dados do repositório encontrados:\n");
        mostrar_tudo_repo(repo_encontrado);
        free(repo_encontrado);
    } else {
        printf("❌ Falha: O repositório '%s' não foi retornado.\n\n", nome_repo);
    }

    // -----------------------------------------------------------------
    // TESTE 3: Módulo de Pacotes (Busca no Gentoo Oficial)
    // -----------------------------------------------------------------
    printf("[TESTE 3] A testar busca de pacote informando obrigatoriamente 'gentoo'...\n");
    PacoteGentoo *pkg_oficial = procurar_pacote("net-firewall", "nftables", "gentoo");
    if (pkg_oficial) {
        printf("✅ Sucesso! Pacote oficial mapeado com as structs:\n");
        mostrar_tudo_pacote(pkg_oficial);
        free(pkg_oficial);
    } else {
        printf("❌ Falha: Não foi possível obter o pacote oficial.\n\n");
    }

    // -----------------------------------------------------------------
    // TESTE 4: Módulo de Pacotes (Busca em Overlay da Comunidade)
    // -----------------------------------------------------------------
    printf("[TESTE 4] A testar busca de pacote informando obrigatoriamente o overlay 'guru'...\n");
    PacoteGentoo *pkg_overlay = procurar_pacote("dev-util", "git-cliff", "guru");
    if (pkg_overlay) {
        printf("✅ Sucesso! Pacote do overlay mapeado com as structs:\n");
        mostrar_tudo_pacote(pkg_overlay);
        free(pkg_overlay);
    } else {
        printf("❌ Falha: Não foi possível obter o pacote do overlay.\n\n");
    }

    // -----------------------------------------------------------------
    // TESTE 5: Módulo de Pacotes (Tratamento de Erros / Pacote Inexistente)
    // -----------------------------------------------------------------
    printf("[TESTE 5] A testar comportamento ao procurar um pacote que não existe...\n");
    PacoteGentoo *pkg_fantasma = procurar_pacote("sys-apps", "pacote-que-nao-existe", "gentoo");
    if (pkg_fantasma == NULL) {
        printf("✅ Sucesso! O sistema tratou o erro 404 corretamente e retornou NULL.\n");
    } else {
        printf("❌ Falha: O sistema deveria ter retornado NULL para um pacote inexistente.\n");
        free(pkg_fantasma);
    }
    printf("----------------------------------------------------------------------\n\n");

    printf("===============================================================\n");
    printf("            TODOS OS TESTES FORAM CONCLUÍDOS!                  \n");
    printf("===============================================================\n");

    // Limpeza de memória global das bibliotecas
    xmlCleanupParser();
    curl_global_cleanup();
    return 0;
}