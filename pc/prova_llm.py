#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Prova de fogo de um modelo local no Ollama — mede, não estima.

Por que existe: "é rápido o suficiente?" não se responde por opinião. O Ollama
devolve, em cada resposta, quantos tokens processou e em quantos nanossegundos.
Este script lê esses contadores e imprime a velocidade REAL, o pico de memória
e se a chamada de ferramenta funciona de verdade — não a promessa do README.

Mede quatro coisas:
  1. velocidade de PROMPT (ler o que você mandou) — limitada por cálculo;
  2. velocidade de GERAÇÃO (escrever a resposta) — limitada por banda de memória;
  3. memória ocupada pelo modelo carregado;
  4. chamada de ferramenta: define uma função de verdade e confere se o modelo
     a invoca com os argumentos certos.

Uso:
    python3 prova_llm.py qwen3:4b
    python3 prova_llm.py qwen3:4b --etiqueta "CPU"        # rotula a rodada
    python3 prova_llm.py qwen3:4b --json saida.json       # salva para comparar depois
    python3 prova_llm.py qwen3:4b --comparar antes.json   # compara com uma rodada anterior

Não escreve nada fora do arquivo --json que você pedir. Exit 0 sempre que o
modelo respondeu; exit 1 se ele nem carregou.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request

OLLAMA = "http://127.0.0.1:11434"

VERDE, AMARELO, VERMELHO, NEGRITO, FIM = "\033[92m", "\033[93m", "\033[91m", "\033[1m", "\033[0m"

# Três prompts fixos em português. Sem dado de paciente — são sintéticos.
PROMPTS = [
    ("curto",
     "Responda em uma única frase: para que serve o escore SOFA na terapia intensiva?"),
    ("resumo",
     "Resuma em no máximo 3 tópicos, em português: 'O paciente evoluiu com queda da "
     "pressão arterial média para 58 mmHg, lactato em ascensão de 2,1 para 4,3 mmol/L "
     "e diurese de 0,3 mL/kg/h nas últimas seis horas. Foi iniciada noradrenalina em "
     "dose baixa e coletadas duas hemoculturas antes do antibiótico.'"),
    ("estrutura",
     "Devolva SOMENTE um objeto JSON válido, sem texto antes ou depois, com as chaves "
     "pam, lactato e diurese, extraídas de: 'PAM 58 mmHg, lactato 4,3 mmol/L, "
     "diurese 0,3 mL/kg/h'."),
]

FERRAMENTA = [{
    "type": "function",
    "function": {
        "name": "registrar_sinal_vital",
        "description": "Registra um sinal vital medido de um paciente no leito informado.",
        "parameters": {
            "type": "object",
            "properties": {
                "leito": {"type": "string", "description": "Identificador do leito, ex: UTI2-L07"},
                "parametro": {"type": "string", "description": "Nome do sinal vital, ex: pam"},
                "valor": {"type": "number", "description": "Valor numérico medido"},
            },
            "required": ["leito", "parametro", "valor"],
        },
    },
}]

PROMPT_FERRAMENTA = ("No leito UTI2-L07 a pressão arterial média está em 58. "
                     "Registre esse sinal vital.")

# Opções enviadas em toda chamada. `--cpu` injeta num_gpu=0 aqui, que força o
# llama.cpp a NÃO descarregar camada nenhuma na placa de vídeo — é assim que se
# compara GPU contra CPU sem reiniciar o serviço.
OPCOES: dict = {}


def opts(extra: dict) -> dict:
    return {**extra, **OPCOES}


def chamar(rota: str, corpo: dict, timeout: int = 900) -> dict:
    req = urllib.request.Request(
        f"{OLLAMA}{rota}",
        data=json.dumps(corpo).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def taxa(tokens: int | None, nanos: int | None) -> float | None:
    """tokens por segundo, ou None se o Ollama não informou."""
    if not tokens or not nanos:
        return None
    return round(tokens / (nanos / 1e9), 2)


def memoria_do_modelo() -> tuple[str, str]:
    """Lê `ollama ps`: quanto o modelo ocupa e onde (CPU/GPU)."""
    try:
        s = subprocess.run(["ollama", "ps"], capture_output=True, text=True, timeout=20).stdout
    except (OSError, subprocess.TimeoutExpired):
        return "?", "?"
    linhas = [l for l in s.splitlines()[1:] if l.strip()]
    if not linhas:
        return "não carregado", "-"
    partes = linhas[0].split()
    tamanho = " ".join(partes[2:4]) if len(partes) > 4 else "?"
    processador = " ".join(partes[4:6]) if len(partes) > 5 else "?"
    return tamanho, processador


def contexto_efetivo(modelo: str) -> str:
    try:
        d = chamar("/api/show", {"model": modelo}, timeout=60)
    except (urllib.error.URLError, OSError, json.JSONDecodeError):
        return "?"
    params = d.get("parameters", "") or ""
    for linha in params.splitlines():
        if linha.strip().startswith("num_ctx"):
            return linha.split()[-1]
    info = d.get("model_info", {}) or {}
    for k, v in info.items():
        if k.endswith(".context_length"):
            return f"{v} (máximo do modelo)"
    return "padrão do servidor"


def rodar(modelo: str) -> dict:
    resultado = {"modelo": modelo, "prompts": [], "ferramenta": None, "erro": None}

    print(f"{NEGRITO}Carregando {modelo}…{FIM}", flush=True)
    t0 = time.time()
    try:
        # `think: False` desliga o bloco de raciocínio dos modelos pensantes
        # (Qwen3 e afins). Sem isso, um "oi" gera centenas de tokens invisíveis
        # e a 4 tokens/s a chamada de aquecimento sozinha leva minutos.
        primeira = chamar("/api/generate", {
            "model": modelo, "prompt": "oi", "stream": False,
            "think": False, "options": opts({"num_predict": 8}),
        })
    except (urllib.error.URLError, OSError) as e:
        resultado["erro"] = f"o modelo não carregou: {e}"
        return resultado
    resultado["carga_s"] = round(primeira.get("load_duration", 0) / 1e9, 1)
    print(f"  carregou em {round(time.time() - t0, 1)} s "
          f"(carga do disco: {resultado['carga_s']} s)")

    tamanho, processador = memoria_do_modelo()
    resultado["memoria"] = tamanho
    resultado["processador"] = processador
    resultado["contexto"] = contexto_efetivo(modelo)
    print(f"  ocupa {tamanho} · rodando em {processador} · contexto {resultado['contexto']}")

    for nome, texto in PROMPTS:
        print(f"\n{NEGRITO}[{nome}]{FIM} {texto[:70]}…", flush=True)
        try:
            r = chamar("/api/chat", {
                "model": modelo,
                "messages": [{"role": "user", "content": texto}],
                "stream": False,
                "think": False,
                "options": opts({"num_predict": 256}),
            })
        except (urllib.error.URLError, OSError) as e:
            resultado["prompts"].append({"nome": nome, "erro": str(e)})
            print(f"  {VERMELHO}falhou: {e}{FIM}")
            continue
        p_tok, p_ns = r.get("prompt_eval_count"), r.get("prompt_eval_duration")
        g_tok, g_ns = r.get("eval_count"), r.get("eval_duration")
        item = {
            "nome": nome,
            "prompt_tokens": p_tok, "prompt_tok_s": taxa(p_tok, p_ns),
            "gerados": g_tok, "geracao_tok_s": taxa(g_tok, g_ns),
            "total_s": round(r.get("total_duration", 0) / 1e9, 1),
            "resposta": (r.get("message", {}).get("content") or "").strip(),
        }
        resultado["prompts"].append(item)
        print(f"  prompt: {p_tok} tokens a {item['prompt_tok_s']} tok/s   |   "
              f"geração: {g_tok} tokens a {NEGRITO}{item['geracao_tok_s']} tok/s{FIM}   |   "
              f"total {item['total_s']} s")
        print(f"  resposta: {item['resposta'][:160]}"
              + ("…" if len(item["resposta"]) > 160 else ""))

    print(f"\n{NEGRITO}[ferramenta]{FIM} o modelo sabe chamar uma função?", flush=True)
    try:
        r = chamar("/api/chat", {
            "model": modelo,
            "messages": [{"role": "user", "content": PROMPT_FERRAMENTA}],
            "tools": FERRAMENTA,
            "stream": False,
            "think": False,
            "options": opts({"num_predict": 256}),
        })
        chamadas = r.get("message", {}).get("tool_calls") or []
        if not chamadas:
            resultado["ferramenta"] = {"ok": False, "motivo": "não chamou nenhuma função",
                                       "texto": (r.get("message", {}).get("content") or "")[:200]}
            print(f"  {VERMELHO}NÃO chamou a função{FIM} — respondeu em texto")
        else:
            args = chamadas[0].get("function", {}).get("arguments", {})
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    pass
            nome_fn = chamadas[0].get("function", {}).get("name")
            correto = (nome_fn == "registrar_sinal_vital"
                       and str(args.get("leito", "")).upper().replace(" ", "") == "UTI2-L07"
                       and abs(float(args.get("valor", 0) or 0) - 58) < 0.01)
            resultado["ferramenta"] = {"ok": bool(correto), "funcao": nome_fn, "argumentos": args}
            cor = VERDE if correto else AMARELO
            print(f"  {cor}chamou {nome_fn}{FIM} com {args}"
                  + ("" if correto else "  <- argumentos NÃO conferem"))
    except (urllib.error.URLError, OSError, ValueError) as e:
        resultado["ferramenta"] = {"ok": False, "motivo": str(e)}
        print(f"  {VERMELHO}falhou: {e}{FIM}")

    return resultado


def resumo(r: dict, etiqueta: str) -> None:
    taxas = [p.get("geracao_tok_s") for p in r["prompts"] if p.get("geracao_tok_s")]
    if not taxas:
        print(f"\n{VERMELHO}Nenhuma medição válida.{FIM}")
        return
    media = round(sum(taxas) / len(taxas), 2)
    r["geracao_media_tok_s"] = media
    print(f"\n{NEGRITO}== RESUMO {etiqueta} =={FIM}")
    print(f"  geração média      {NEGRITO}{media} tok/s{FIM}  (≈ {round(media * 0.75, 1)} palavras/s)")
    print(f"  memória ocupada    {r.get('memoria')}")
    print(f"  processador        {r.get('processador')}")
    print(f"  contexto           {r.get('contexto')}")
    fer = r.get("ferramenta") or {}
    print(f"  chamada de função  {'FUNCIONA' if fer.get('ok') else 'FALHOU'}")
    if media >= 8:
        print(f"  veredito           {VERDE}usável para conversa{FIM}")
    elif media >= 4:
        print(f"  veredito           {AMARELO}lento, serve para tarefa curta e para lote{FIM}")
    else:
        print(f"  veredito           {VERMELHO}lento demais para uso interativo{FIM}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Mede um modelo local do Ollama.")
    ap.add_argument("modelo", help="tag do modelo, ex: qwen3:4b")
    ap.add_argument("--etiqueta", default="", help="rótulo desta rodada, ex: CPU ou Vulkan")
    ap.add_argument("--json", help="salva o resultado neste arquivo")
    ap.add_argument("--comparar", help="compara com o resultado salvo de uma rodada anterior")
    ap.add_argument("--cpu", action="store_true",
                    help="força CPU pura (num_gpu=0), para comparar contra a placa de vídeo")
    a = ap.parse_args()

    if a.cpu:
        OPCOES["num_gpu"] = 0

    r = rodar(a.modelo)
    if r.get("erro"):
        print(f"{VERMELHO}{r['erro']}{FIM}")
        return 1
    resumo(r, a.etiqueta)

    if a.comparar:
        try:
            antes = json.load(open(a.comparar, encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            print(f"{AMARELO}não consegui ler {a.comparar}: {e}{FIM}")
        else:
            v0, v1 = antes.get("geracao_media_tok_s"), r.get("geracao_media_tok_s")
            if v0 and v1:
                delta = round((v1 / v0 - 1) * 100, 1)
                cor = VERDE if delta > 3 else (VERMELHO if delta < -3 else AMARELO)
                print(f"\n{NEGRITO}== COMPARAÇÃO =={FIM}")
                print(f"  antes  {v0} tok/s   agora  {v1} tok/s   "
                      f"{cor}{'+' if delta >= 0 else ''}{delta}%{FIM}")

    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump(r, f, ensure_ascii=False, indent=2)
        print(f"\nresultado salvo em {a.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
