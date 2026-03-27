import logging
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import get_settings
from schemas import AnalyzeRequest, AnalyzeResponse
from cache import cache
from analyzers import (
    analyze_language,
    analyze_sources,
    analyze_domain,
    classify_page_type,
    detect_misinfo_patterns,
)
from scoring import compute_final_score


# ============================
# LOGGING
# ============================
settings = get_settings()
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("trustlens")


# ============================
# APP LIFESPAN
# ============================
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("TrustLens API starting up")
    logger.info(f"OpenAI model: {settings.openai_model}")
    logger.info(f"LLM enabled: {bool(settings.openai_api_key)}")
    yield
    logger.info("TrustLens API shutting down")


# ============================
# FASTAPI APP
# ============================
app = FastAPI(
    title="TrustLens API",
    description="Misinformation risk analysis backend",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — pozwól extension na łączenie się
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================
# HEALTH CHECK
# ============================
@app.get("/")
async def root():
    return {
        "service": "TrustLens API",
        "status": "running",
        "version": "1.0.0",
        "llm_enabled": bool(settings.openai_api_key),
        "cache_size": cache.size,
    }


@app.get("/health")
async def health():
    return {"status": "ok"}


# ============================
# MAIN ANALYZE ENDPOINT
# ============================
@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze(request: AnalyzeRequest):
    """
    Główny endpoint — przyjmuje dane strony, zwraca analizę ryzyka.
    """
    url = request.url

    if not url:
        raise HTTPException(status_code=400, detail="URL is required")

    # ---- Cache check ----
    cached = cache.get(url)
    if cached is not None:
        logger.info(f"Cache hit: {url[:80]}")
        return cached

    logger.info(f"Analyzing: {url[:80]}")

    # ---- Sanitize input ----
    text = (request.text or "")[:settings.max_text_length]
    title = (request.title or "")[:300]
    links = (request.links or [])[:settings.max_links]
    meta = request.meta.model_dump() if request.meta else {}

    try:
        # ============================
        # STEP 1: Run independent analyses in parallel
        # ============================
        # Language + Sources = synchroniczne, ale szybkie
        # Domain + LLM page type = async, mogą trwać dłużej
        
        language_result = await analyze_language(text, title)
        source_result = analyze_sources(url, links, meta, text)

        # Zbierz sygnały heurystyczne dla LLM
        heuristic_signals = language_result.signals + source_result.signals

        # Async tasks — domain + LLM page type równolegle
        domain_task = analyze_domain(url)
        page_type_task = classify_page_type(title, text, meta)

        domain_result, page_type_result = await asyncio.gather(
            domain_task,
            page_type_task,
        )

        # Dodaj domain signals do heuristic_signals
        heuristic_signals.extend(domain_result.signals)

        # ============================
        # STEP 2: Misinfo pattern detection (potrzebuje wyników z kroku 1)
        # ============================
        misinfo_result = await detect_misinfo_patterns(
            title=title,
            text=text,
            meta=meta,
            heuristic_signals=heuristic_signals,
        )

        # ============================
        # STEP 3: Compute final score
        # ============================
        response = compute_final_score(
            language=language_result,
            sources=source_result,
            domain=domain_result,
            page_type_result=page_type_result,
            misinfo_result=misinfo_result,
            url=url,
        )

        # ---- Cache result ----
        cache.set(url, response)

        logger.info(
            f"Done: {url[:60]} → risk={response.overall_risk} "
            f"type={response.page_type.label} "
            f"patterns={response.misinfo_patterns}"
        )

        return response

    except Exception as e:
        logger.error(f"Analysis error for {url[:80]}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Analysis failed: {str(e)}",
        )


# ============================
# BATCH ENDPOINT (bonus)
# ============================
@app.post("/analyze/batch")
async def analyze_batch(requests: list[AnalyzeRequest]):
    """Batch analysis — max 5 URLs at once."""
    if len(requests) > 5:
        raise HTTPException(status_code=400, detail="Maximum 5 URLs per batch")

    tasks = [analyze(req) for req in requests]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    responses = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            responses.append({
                "url": requests[i].url,
                "error": str(result),
            })
        else:
            responses.append(result)

    return responses


# ============================
# CACHE MANAGEMENT
# ============================
@app.delete("/cache")
async def clear_cache():
    """Czyści cache (przydatne przy testach)."""
    cache.clear()
    return {"status": "cache cleared"}


# ============================
# RUN
# ============================
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.port,
        reload=True,
        log_level=settings.log_level,
    )