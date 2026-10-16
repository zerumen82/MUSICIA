"""Proceso residente del traductor de estilo.

Lo arranca el Python del motor, que es el que tiene torch. Este proceso no
importa el backend: lee una orden JSON por línea y escribe una respuesta JSON
por línea. El modelo se carga una vez.
"""

from __future__ import annotations

import argparse
import json
import sys


def _read_request():
    line = sys.stdin.readline()
    if not line:
        return None
    line = line.strip()
    if not line:
        return {}
    return json.loads(line)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--device", required=True)
    parser.add_argument("--max-input-tokens", type=int, required=True)
    parser.add_argument("--max-new-tokens", type=int, required=True)
    parser.add_argument("--num-beams", type=int, required=True)
    parser.add_argument("--do-sample", choices=("true", "false"), required=True)
    args = parser.parse_args()
    real_out = sys.stdout
    sys.stdout = sys.stderr
    try:
        import torch
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

        tokenizer = AutoTokenizer.from_pretrained(args.model)
        model = AutoModelForSeq2SeqLM.from_pretrained(args.model)
        model.to(args.device)
        model.eval()
    except Exception as exc:  # noqa: BLE001 - el padre tiene que ver el fallo de carga
        sys.stdout = real_out
        real_out.write(json.dumps({"ready": False, "error": str(exc)}) + "\n")
        real_out.flush()
        return 1
    sys.stdout = real_out
    real_out.write(json.dumps({"ready": True}) + "\n")
    real_out.flush()
    do_sample = args.do_sample == "true"
    while True:
        try:
            request = _read_request()
        except json.JSONDecodeError as exc:
            real_out.write(json.dumps({"id": None, "error": f"orden ilegible: {exc}"}) + "\n")
            real_out.flush()
            continue
        if request is None:
            return 0
        if not request:
            continue
        identity = request.get("id")
        try:
            text = str(request.get("text") or "")
            source = str(request.get("source_lang") or "")
            target = str(request.get("target_lang") or "")
            if not text.strip():
                translated = ""
            elif source == target:
                translated = text.strip()
            else:
                tokenizer.src_lang = source
                encoded = tokenizer(
                    text, return_tensors="pt", truncation=True, max_length=args.max_input_tokens,
                )
                encoded = {key: value.to(args.device) for key, value in encoded.items()}
                forced = tokenizer.convert_tokens_to_ids(target)
                if forced == tokenizer.unk_token_id:
                    raise ValueError(f"código de idioma desconocido para el modelo: {target}")
                with torch.no_grad():
                    generated = model.generate(
                        **encoded,
                        forced_bos_token_id=forced,
                        max_new_tokens=args.max_new_tokens,
                        num_beams=args.num_beams,
                        do_sample=do_sample,
                    )
                translated = tokenizer.batch_decode(generated, skip_special_tokens=True)[0].strip()
            real_out.write(json.dumps({"id": identity, "text": translated}) + "\n")
        except Exception as exc:  # noqa: BLE001 - una frase no puede tumbar el proceso
            real_out.write(json.dumps({"id": identity, "error": str(exc)}) + "\n")
        real_out.flush()


if __name__ == "__main__":
    raise SystemExit(main())
