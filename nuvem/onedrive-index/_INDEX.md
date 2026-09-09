# Arquivo de documentos — Dr. Nicolas Nagaita

> Catálogo agente-first · reorganizado 2026-07-05 **por feature** (o que o documento é, não a data).
> **855 arquivos** em 10 features · datas reais 2005-02-20–2026-07-03 · raiz
> `OneDrive:/Documentos-claude-e-importacao-drive/`.

## Como usar (IA e humano)

- Cada arquivo é agrupado por **feature** (pasta) e nomeado `categoria_assunto[_paciente][_data].ext`.
- A **data só aparece quando é real** — nada de estimativa. Ordenação natural = por assunto, não por tempo.
- `_index.json` = índice-máquina: todo arquivo com feature/categoria/data/paciente/phi.
- 🔴 PHI: arquivos clínicos têm nome completo de paciente.
- Dumps de código em `Dev-IA/_codigo-backup/` (o código canônico vive no GitHub).
- Originais no Google Drive como backup.

## Features (pastas nível 1)

| Feature                                                | Arquivos |
| ------------------------------------------------------ | -------- |
| **Clínico** (`Clinico/`)                               | 314      |
| **Estudo** (`Estudo/`)                                 | 177      |
| **Dev-IA** (`Dev-IA/`)                                 | 131      |
| **Financeiro** (`Financeiro/`)                         | 109      |
| **Militar-FAB** (`Militar-FAB/`)                       | 54       |
| **Tese-Mãe** (`Tese-Mae/`)                             | 30       |
| **Pessoal** (`Pessoal/`)                               | 21       |
| **Passagem de turno** (`Passagem-de-turno/`)           | 11       |
| **Evoluções SASI (Claude)** (`evolucoes-sasi-claude/`) | 7        |
| **Outros** (`Outros/`)                                 | 1        |

## Categorias (tipo de documento)

| Categoria                    | Arquivos | PHI |
| ---------------------------- | -------- | --- |
| Cadastro/Doc (`cadastro`)    | 144      |     |
| Estudo (`estudo`)            | 116      |     |
| Prontuário (`prontuario`)    | 105      | 🔴  |
| Dev/Código (`dev`)           | 103      |     |
| outros (`outros`)            | 95       |     |
| Pessoal (`pessoal`)          | 47       |     |
| Exame (`exame`)              | 38       | 🔴  |
| Passagem (`passagem`)        | 32       | 🔴  |
| Evolução (`evolucao`)        | 30       | 🔴  |
| Auditoria (`auditoria`)      | 30       | 🔴  |
| IA/Prompts (`ia`)            | 25       |     |
| Alto custo (`altocusto`)     | 24       | 🔴  |
| Admissão (`admissao`)        | 18       | 🔴  |
| Financeiro (`financ`)        | 11       |     |
| Laudo/Relatório (`laudo`)    | 11       | 🔴  |
| Solicitação (`solicitacao`)  | 10       | 🔴  |
| Modelo/Template (`modelo`)   | 8        |     |
| Receita/Atestado (`receita`) | 7        | 🔴  |
| Censo (`censo`)              | 1        | 🔴  |

## Índice de pacientes (117)

> Nome → arquivos. Só os que o conteúdo/nome revelou (zero alucinação).

- **ANNITO CHEQUER NOVAES NETO** (1): `exame_tc-abdome-pelve_annito-chequer-novaes-neto_2025-06-11.pdf`
- **BENEDITO AUGUSTO MARCONDES** (1): `exame_tc-abdome-total_benedito-augusto-marcondes_2025-06-18.pdf`
- **EVANIRA APARECIDA DE SANT ANNA FILIPINI** (2):
  `laudo_relatorio-prorrogacao-internacao-fab_evanira-aparecida-de-sant-anna-filipini_2024-11-07.pdf` ·
  `solicitacao_justificativa-nutricao-cuidados-paliativos_evanira-aparecida-de-sant-anna-filipini_2024-12-02.pdf`
- **IAN SERGIO DE SOUZA** (1): `prontuario_folha-observacao-uti_ian-sergio-de-souza.pdf`
- **IVAN LUIZ DE CASTRO NOBRE** (1): `exame_tc-abdome-pelve_ivan-luiz-de-castro-nobre_2025-06-22.pdf`
- **JOAO BOSCO DE CASTRO NOGUEIRA** (1): `prontuario_fibrose-pulmonar-dpoc-ic_joao-bosco-de-castro-nogueira.docx`
- **LAERTE GONCALVES PEREIRA** (1): `exame_tc-abdome-pelve_laerte-goncalves-pereira_2025-06-21.pdf`
- **LUIS ANTONIO BENEDITO** (4): `cadastro_funsa_luis-antonio-benedito.docx` ·
  `cadastro_funsa_luis-antonio-benedito.rtf` · `cadastro_resumido-rtf_luis-antonio-benedito.docx` ·
  `laudo_relatorio-internacao_luis-antonio-benedito_2024-05-27.pdf`
- **MAE** (1): `prontuario_eda-colono-polipos-gastrite_mae_2024-10-27.docx`
- **MARCELA CARDOSO FERNANDES** (1): `receita_atestado-consulta-domiciliar_marcela-cardoso-fernandes_2026-02-19.pdf`
- **MARIA ROSARIA URBANO GOMES** (1): `exame_tc-abdome-total_maria-rosaria-urbano-gomes_2025-06-20.pdf`
- **MARLON RONALDO DE CAMPOS** (1): `exame_tc-abdome-total_marlon-ronaldo-de-campos_2025-06-21.pdf`
- **MATEUS ELIAS DE JESUS MELLO** (1): `cadastro_rg-militar-fab_mateus-elias-de-jesus-mello.jpeg`
- **MINERVINA MARIA DA SILVA CRUZ** (1): `exame_tc-abdome-total_minervina-maria-da-silva-cruz_2025-06-15.pdf`
- **NEUZA COUTO DE MOURA** (1): `exame_tc-cranio_neuza-couto-de-moura_2025-06-20.pdf`
- **NEY AUGUSTO MELLO JUNIOR** (1): `cadastro_atestado-militar-eear_ney-augusto-mello-junior.pdf`
- **PAULO VITOR DIAS** (2): `admissao_admissao_paulo-vitor-dias_2026-05-18.pdf` ·
  `exame_tc-abdome-pelve_paulo-vitor-dias_2026-05-16.pdf`
- **SAULO CASTRO ALMEIDA** (1): `prontuario_tep-bilateral_saulo-castro-almeida.pdf`
- **TEREZA FERRAZ DE CAMPOS SILVA** (1): `exame_tc-abdome-pelve_tereza-ferraz-de-campos-silva_2025-06-14.pdf`
- **VANESSA VEGA DA SILVA ROSA** (1): `receita_prescricao_vanessa-vega-da-silva-rosa_2026-05-20.pdf`
- **WALTER OLIVEIRA DA SILVA** (1):
  `solicitacao_transferencia-cirurgia-cardiaca_walter-oliveira-da-silva_2024-10-20.docx`
- **abner cainan malvao santos** (1): `prontuario_documento_abner-cainan-malvao-santos.docx`
- **achados perdidos bp scs** (23): `prontuario_00-ferramentas-calculadoras-ref_achados-perdidos-bp-scs.xlsx` ·
  `prontuario_0000-folha-rosto-exames_achados-perdidos-bp-scs.xls` ·
  `prontuario_achados-e-perdidos-bp-scs_achados-perdidos-bp-scs.doc` ·
  `prontuario_achados-e-perdidos-bp-scs_achados-perdidos-bp-scs.xlsx` …
- **alberto ferreira freire** (1): `prontuario_documento_alberto-ferreira-freire.docx`
- **altair farias** (1): `prontuario_documento_altair-farias.docx`
- **ana aparecida raimundo** (1): `prontuario_documento_ana-aparecida-raimundo.docx`
- **ana clara peres santos** (1): `prontuario_documento_ana-clara-peres-santos.docx`
- **ana garcez dunder** (1): `prontuario_documento_ana-garcez-dunder.docx`
- **anesia nobrega totaro** (1): `prontuario_documento_anesia-nobrega-totaro.docx`
- **antenor gomes** (1): `admissao_documento_antenor-gomes.docx`
- **antonio vieira** (1): `prontuario_pinto_antonio-vieira.docx`
- **ari ailton molero** (1): `prontuario_martins_ari-ailton-molero.docx`
- **atendimentos comuns prontos** (1): `prontuario_documento_atendimentos-comuns-prontos.docx`
- **beth solange monteiro villela** (1): `altocusto_documento_beth-solange-monteiro-villela.docx`
- **brenda stefani** (2): `altocusto_2_brenda-stefani.docx` · `altocusto_documento_brenda-stefani.docx`
- **bruna larissa** (1): `altocusto_documento_bruna-larissa.docx`
- **caderno gasometria** (2): `clinico_gemini-gems_caderno-gasometria.pdf` · `exame_1_caderno-gasometria.pdf`
- **caderno prof vermelho cad** (1): `exame_documento_caderno-prof-vermelho-cad.pdf`
- **carlos alberto castro** (2): `pessoal_001_carlos-alberto-castro.pdf` ·
  `prontuario_documento_carlos-alberto-castro.docx`
- **cassio nascimento alves atendimento** (1): `laudo_documento_cassio-nascimento-alves-atendimento.docx`
- **celso beise** (1): `prontuario_documento_celso-beise.docx`
- **censo internacoes** (1): `admissao_censo-internacoes-gsau-gw-02-02-25_censo-internacoes_2025-02-02.docx`
- **classificacao risco** (1): `admissao_documento_classificacao-risco.pdf`
- **cleire aparecida barbosa cavalca** (3): `altocusto_16-09-24_cleire-aparecida-barbosa-cavalca_2024-10-17.docx` ·
  `auditoria_documento_cleire-aparecida-barbosa-cavalca.docx` ·
  `auditoria_documento_cleire-aparecida-barbosa-cavalca_2024-09-30.docx`
- **dengue receita logo fab novo** (1): `prontuario_documento_dengue-receita-logo-fab-novo.pdf`
- **dinarte rosa jejus** (1): `prontuario_documento_dinarte-rosa-jejus.docx`
- **edson ambrosio ribeiro** (1): `prontuario_documento_edson-ambrosio-ribeiro_2024-11-14.docx`
- **elizabeth batalha bastos** (2): `auditoria_documento_elizabeth-batalha-bastos_2024-08-20.docx` ·
  `prontuario_documento_elizabeth-batalha-bastos_2024-08-20.docx`
- **exames lab** (3): `cadastro_funsa-walter-oliveira-da-silva_exames-lab.pdf` · `cadastro_walter_exames-lab` ·
  `prontuario_documento_exames-lab.docx`
- **francisco theodoro nobre** (1): `laudo_documento_francisco-theodoro-nobre.docx`
- **funsa gsaugw** (2): `ia_exemplo-padrao_funsa-gsaugw.docx` · `pessoal_documento_funsa-gsaugw.pdf`
- **gabriel henrique silva** (1): `prontuario_documento_gabriel-henrique-silva.docx`
- **gerencial fisio setembro** (1): `cadastro_cristovam-gerencial-fisio-setembro-2024_gerencial-fisio-setembro`
- **ggogins codigo** (1): `prontuario_documento_ggogins-codigo.txt`
- **gustavo augusto alves souza** (1): `altocusto_documento_gustavo-augusto-alves-souza.docx`
- **ismair jesus** (1): `prontuario_documento_ismair-jesus.docx`
- **ivone goncalves gusmao leao** (1): `prontuario_documento_ivone-goncalves-gusmao-leao.docx`
- **joao luiz ribeiro melo** (2): `altocusto_documento_joao-luiz-ribeiro-melo.docx` ·
  `auditoria_documento_joao-luiz-ribeiro-melo.docx`
- **joaquim franca mello** (2): `altocusto_documento_joaquim-franca-mello.docx` ·
  `auditoria_documento_joaquim-franca-mello.docx`
- **jose benedito fortunato** (3): `altocusto_documento_jose-benedito-fortunato_2024-09-29.docx` ·
  `auditoria_documento_jose-benedito-fortunato_2024-09-29.docx` · `prontuario_documento_jose-benedito-fortunato.docx`
- **jose benedito santana** (5): `altocusto_documento_jose-benedito-santana-01.docx` ·
  `altocusto_documento_jose-benedito-santana-02.docx` · `auditoria_documento_jose-benedito-santana-01.docx` ·
  `auditoria_documento_jose-benedito-santana-02.docx` …
- **jose bento cyrino junior** (1): `prontuario_documento_jose-bento-cyrino-junior.docx`
- **jose carlos evaristo** (1): `exame_documento_jose-carlos-evaristo`
- **juraci gabriel souza** (1): `prontuario_juraci-gabriel-souza-pe-diabetico_juraci-gabriel-souza.docx`
- **kaylane kely dos santos reis** (1): `altocusto_documento_kaylane-kely-dos-santos-reis.docx`
- **lenice maria silva alciprett** (4): `altocusto_documento_lenice-maria-silva-alciprett_2024-08-15.docx` ·
  `auditoria_12-08-24_lenice-maria-silva-alciprett_2024-08-12.docx` ·
  `auditoria_12-08-24_lenice-maria-silva-alciprett_2024-08-15.docx` ·
  `auditoria_documento_lenice-maria-silva-alciprett.docx`
- **liz helena** (2): `altocusto_13-06_liz-helena.docx` · `auditoria_almeida-teixeira13-06_liz-helena.docx`
- **lucas felipe** (1): `prontuario_documento_lucas-felipe.pdf`
- **luciano regis campos tonini** (1): `admissao_documento_luciano-regis-campos-tonini.docx`
- **luis antonio ferri** (1): `altocusto_documento_luis-antonio-ferri_2024-07-18.docx`
- **major teodoro cateterismo** (1): `exame_documento_major-teodoro-cateterismo.jpg`
- **manuel rodrigues pereira** (1): `prontuario_documento_manuel-rodrigues-pereira.docx`
- **maria clara silva lemes** (3): `altocusto_documento_maria-clara-silva-lemes_2024-09-29.docx` ·
  `auditoria_documento_maria-clara-silva-lemes_2024-09-19.docx` ·
  `auditoria_documento_maria-clara-silva-lemes_2024-09-29.docx`
- **maria silva** (1): `prontuario_documento_maria-silva.pdf`
- **maria terezinha** (1): `prontuario_documento_maria-terezinha.pdf`
- **marlene ribeiro guimaraes** (1): `altocusto_documento_marlene-ribeiro-guimaraes.docx`
- **matheus augusto souza** (2): `admissao_documento_matheus-augusto-souza.docx` ·
  `prontuario_documento_matheus-augusto-souza.docx`
- **milton cesar oliveira** (1): `prontuario_documento_milton-cesar-oliveira.docx`
- **minervina maria silva cruz** (1): `prontuario_documento_minervina-maria-silva-cruz.docx`
- **neuza couto moura** (1): `prontuario_documento_neuza-couto-moura.docx`
- **nicholas frede carvalho silva** (1): `prontuario_documento_nicholas-frede-carvalho-silva.docx`
- **nipo beiseboro** (1): `prontuario_vsf-kkkkk-a-que-pontos-chegamos-eu-ter-q_nipo-beiseboro.xlsx`
- **odilia alice silva** (1): `prontuario_documento_odilia-alice-silva.docx`
- **olga pereira** (1): `prontuario_documento_olga-pereira.docx`
- **paulo cesar oliveira** (1): `prontuario_documento_paulo-cesar-oliveira.docx`
- **paulo henrique** (1): `prontuario_documento_paulo-henrique.docx`
- **pedido jose benedito fortunato** (1): `prontuario_documento_pedido-jose-benedito-fortunato.docx`
- **porfirio joaquim silva neto** (1): `prontuario_documento_porfirio-joaquim-silva-neto.docx`
- **rafaela camila di giovani** (3): `altocusto_documento_rafaela-camila-di-giovani-01.docx` ·
  `altocusto_documento_rafaela-camila-di-giovani-02.docx` · `auditoria_documento_rafaela-camila-di-giovani.docx`
- **rafaela camila di giovani oliveira** (3): `altocusto_documento_rafaela-camila-di-giovani-oliveira.docx` ·
  `auditoria_documento_rafaela-camila-di-giovani-oliveira.docx` ·
  `prontuario_rafaela-camila-di-giovani_rafaela-camila-di-giovani-oliveira.docx`
- **receita controlada lorena** (1): `prontuario_documento_receita-controlada-lorena.odt`
- **receita guei** (1): `prontuario_documento_receita-guei`
- **renata helena carvalho guimaraes** (1): `altocusto_documento_renata-helena-carvalho-guimaraes.docx`
- **resumo claudia helena amaro silva** (1): `prontuario_documento_resumo-claudia-helena-amaro-silva.docx`
- **resumo clidenor andrade lucena** (1): `prontuario_documento_resumo-clidenor-andrade-lucena.docx`
- **rodovan benedito lima filho** (1): `prontuario_documento_rodovan-benedito-lima-filho.docx`
- **rodovan shirley aparecida barbosa** (1): `solicitacao_documento_rodovan-shirley-aparecida-barbosa_2024-10-31.docx`
- **rodovan walter oliveira silva** (1): `prontuario_documento_rodovan-walter-oliveira-silva_2024-10-20.docx`
- **rodrigo augusto aguiar** (1): `prontuario_documento_rodrigo-augusto-aguiar.docx`
- **shirley aparecida** (1): `solicitacao_documento_shirley-aparecida_2024-10-31.docx`
- **shirley aparecida barbosa** (1): `prontuario_documento_shirley-aparecida-barbosa.docx`
- **shirley martiniano** (1): `laudo_documento_shirley-martiniano.odt`
- **stefany reis** (3): `exame_1_stefany-reis.pdf` · `exame_2_stefany-reis.pdf` · `exame_documento_stefany-reis.pdf`
- **stefany reis simoes dos** (1): `prontuario_stefany-reis-simoes-dos-santos_stefany-reis-simoes-dos.docx`
- **taina coelho ferreira** (1): `prontuario_documento_taina-coelho-ferreira.docx`
- **tereza diniz conceicao** (1): `prontuario_documento_tereza-diniz-conceicao.docx`
- **tereza ferraz campos silva** (1): `prontuario_documento_tereza-ferraz-campos-silva.docx`
- **thaina coelho ferreira** (1): `prontuario_documento_thaina-coelho-ferreira.docx`
- **thais aparecida morais freire** (1): `prontuario_documento_thais-aparecida-morais-freire.docx`
- **thalita aparecida** (1): `prontuario_documento_thalita-aparecida.pdf`
- **thalles vieira lemos** (1): `prontuario_documento_thalles-vieira-lemos.docx`
- **tiago luis alvarenga caldas moreira** (1): `prontuario_documento_tiago-luis-alvarenga-caldas-moreira.docx`
- **tomazia maria conceicao souza** (1): `prontuario_documento_tomazia-maria-conceicao-souza.docx`
- **vera lucia mariano** (2): `exame_documento_vera-lucia-mariano_2025-02-12` ·
  `exame_documento_vera-lucia-mariano_2025-02-12.pdf`
- **waldemir benedito mota guedes** (1): `exame_documento_waldemir-benedito-mota-guedes`
- **walter oliveira silva** (2): `auditoria_documento_walter-oliveira-silva_2024-10-20.docx` ·
  `prontuario_documento_walter-oliveira-silva.docx`
- **wilson luiz duarte** (1): `prontuario_documento_wilson-luiz-duarte.docx`
