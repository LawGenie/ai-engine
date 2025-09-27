import asyncio
import json
from pathlib import Path
import sys
import os
from dotenv import load_dotenv

# Ensure ai-engine root is on sys.path
CURRENT_FILE = Path(__file__).resolve()
AI_ENGINE_ROOT = CURRENT_FILE.parents[1]
if str(AI_ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_ENGINE_ROOT))

# Load .env from ai-engine root
env_path = AI_ENGINE_ROOT / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=str(env_path))

from app.models.requirement_models import RequirementAnalysisRequest
from workflows.requirements_workflow import RequirementsWorkflow
from workflows.tools import RequirementsTools


async def run_once(use_openai: bool, hs_code: str, product_name: str):
    # Toggle keyword extraction mode via env (in-process)
    if use_openai:
        os.environ["USE_OPENAI_KEYWORDS"] = "true"
        os.environ.setdefault("OPENAI_KEYWORDS_MODEL", "gpt-4o-mini")
    else:
        os.environ["USE_OPENAI_KEYWORDS"] = "false"

    mode = "openai_on" if use_openai else "openai_off"
    print(f"\n=== Running RequirementsWorkflow ({mode}) ===")

    wf = RequirementsWorkflow()
    req = RequirementAnalysisRequest(hs_code=hs_code, product_name=product_name, product_description="cosmetics")
    resp = await wf.analyze_requirements(req)
    print("Answer:", resp.answer)
    print("Certs:", len(resp.requirements.certifications), "Docs:", len(resp.requirements.documents))

    print("\n=== Testing Tools: CBP precedents ===")
    tools = RequirementsTools()
    cbp = await tools.get_cbp_precedents(hs_code)
    print("CBP precedents count:", cbp.get("count"))

    print("\n=== Testing Tools: PDF summarizer (sample) ===")
    pdf_url = "https://www.fda.gov/media/80637/download"
    pdf = await tools.summarize_pdf(pdf_url)
    print("PDF summary keys:", list(pdf.keys()))

    out = {
        "mode": mode,
        "workflow_answer": resp.answer,
        "certifications": [c.model_dump() for c in resp.requirements.certifications],
        "documents": [d.model_dump() for d in resp.requirements.documents],
        "metadata": resp.metadata.model_dump(),
        "cbp": cbp,
        "pdf": pdf,
    }
    Path("test_outputs").mkdir(exist_ok=True)
    out_path = Path(f"test_outputs/requirements_test_{mode}.json")
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nSaved: {out_path}")


async def main():
    hs_code = "3304.99.50.00"
    product_name = "Vitamin C Serum"
    await run_once(False, hs_code, product_name)
    await run_once(True, hs_code, product_name)


if __name__ == "__main__":
    asyncio.run(main())


