#!/usr/bin/env python3
import os
import argparse
import pandas as pd
from process import alert, site, common_area, call_queue, device, auto_receptionist, routing_rule, shared_line_group, tts_prompt
from process.line_key import generate_line_key_report
from migrator.utils import find_excel_files, ALERT_EMAILS


TEMPLATE_PATH = "templates/Zeus_HEB_Zoom_Site_Template.xlsx"


def process(input_dir: str, output_path: str) -> None:
    # Decide where all side‑car files (csv / xlsx / TTS folders) will live.
    # If the user gave “--output Foo.xlsx” we default to “output/”.
    base_dir = os.path.dirname(output_path) or "output"
    os.makedirs(base_dir, exist_ok=True)

    if not os.path.isfile(TEMPLATE_PATH):
        raise FileNotFoundError(f"Template not found at {TEMPLATE_PATH}")

    with pd.ExcelWriter(output_path, engine="xlsxwriter") as writer:
        # copy template sheets first
        for sheet in pd.ExcelFile(TEMPLATE_PATH).sheet_names:
            pd.read_excel(TEMPLATE_PATH, sheet_name=sheet).to_excel(
                writer, sheet_name=sheet, index=False
            )

        # iterate through every discovery doc found in *input_dir*
        for file_path in find_excel_files(input_dir):
            corp = os.path.basename(file_path).split()[1]

            # ── build / write the regular Zeus sheets ─────────────────
            site.write(site.build(input_dir), writer)
            ca_df = common_area.build(input_dir)
            common_area.write(ca_df, writer)
            call_queue_df = call_queue.build(input_dir)
            call_queue.write(call_queue_df, writer)
            device.write(device.build(input_dir), writer)
            alert.write(alert.build(input_dir, ALERT_EMAILS), writer)
            auto_receptionist.write(auto_receptionist.build(input_dir), writer)
            routing_rule.write(routing_rule.build(input_dir), writer)
            slg_df = shared_line_group.build(input_dir)
            shared_line_group.write(slg_df, writer)

            generate_line_key_report(
                corp,
                ca_df.to_dict(orient="records"),
                base_dir,
            )

            cq_csv = os.path.join(base_dir, f"CORP_{corp}_call_queues.csv")
            call_queue_df.to_csv(cq_csv, index=False)

            slg_csv = os.path.join(base_dir, f"CORP_{corp}_shared_line_groups.csv")
            slg_df.to_csv(slg_csv, index=False)

            tts_output_dir = os.path.join(os.getcwd(), "tts_input")
            os.makedirs(tts_output_dir, exist_ok=True)
            tts_prompt.generate_tts_files(input_dir, tts_output_dir)

            lk_xlsx = os.path.join(base_dir, f"CORP_{corp}_Line_Keys.xlsx")

            print(f"Line Keys   → {lk_xlsx}")
            print(f"Call Queues → {cq_csv}")
            print(f"Shared Line Groups   → {slg_csv}")
            print(f"TTS prompts → {tts_output_dir}")


def main():
    parser = argparse.ArgumentParser(description="Zeus Discovery Doc Processor - HEB Edition")
    parser.add_argument("--input", default="input", help="Input folder path")
    parser.add_argument("--output", default="output", help="Output folder path")

    args = parser.parse_args()

    process(args.input, args.output)


if __name__ == "__main__":
    main()