from __future__ import annotations

"""Recomendador de precios via TF-IDF + similitud coseno."""

from typing import Any
import unicodedata
import threading
import logging

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from sentence_transformers import SentenceTransformer


bitacora = logging.getLogger("daad-backend")

# Similitud coseno
_SIMILITUD_MINIMA: float = 0.10
_LIMITE_SIMILARES: int = 10
_MINIMO_ROBUSTO: int = 3


def _normalizar_texto(valor: object | None) -> str:
    import re

    if valor is None:
        return ""

    texto = str(valor).lower()

    texto_nfd = unicodedata.normalize("NFD", texto)

    sin_acentos = "".join(
        c for c in texto_nfd
        if unicodedata.category(c) != "Mn"
    )

    sin_acentos = re.sub(
        r"[^a-z0-9 ]",
        " ",
        sin_acentos
    )

    return " ".join(sin_acentos.split())


class RecomendadorPrecio:
    """Recomienda precio por similitud semantica TF-IDF + coseno + promedio ponderado."""

    def __init__(self) -> None:
        self._modelo: SentenceTransformer | None = None
        self._embeddings: np.ndarray | None = None       
        self._catalogo: list[dict[str, Any]] = []
        self._firma: int | None = None
        self._candado = threading.Lock()

    # ------------------------------------------------------------------
    # Métodos privados — construcción del índice
    # ------------------------------------------------------------------

    def _extraer_atributos_producto(self, producto: dict[str, Any]) -> dict[str, float]:
        import re
        atributos = {}
        texto = f"{producto.get('nombre', '')} {producto.get('marca', '')}".lower()
        
        # Pulgadas
        match_pulgadas = re.search(r"\b(\d+(?:\.\d+)?)\s*(?:\"|''|pulgada|pulgadas|inch|inches)\b", texto)
        if match_pulgadas:
            atributos['pulgadas'] = float(match_pulgadas.group(1))
            
        # GB / TB / MB
        match_almacenamiento = re.search(r"\b(\d+(?:\.\d+)?)\s*(gb|tb|mb)\b", texto)
        if match_almacenamiento:
            val = float(match_almacenamiento.group(1))
            unidad = match_almacenamiento.group(2)
            if unidad == 'tb': val *= 1024
            elif unidad == 'mb': val /= 1024
            atributos['almacenamiento_gb'] = val
            
        return atributos

    def _construir_documento(self, producto: dict[str, Any]) -> str:
        nombre = _normalizar_texto(producto.get("nombre"))
        marca = _normalizar_texto(producto.get("marca"))
        categoria = _normalizar_texto(producto.get("categoria"))

        # Dar mayor peso al nombre
        partes = [nombre, marca, categoria]

        return " ".join(p for p in partes if p) or "producto"

    

    def _asegurar_indice(self) -> None:
        """Carga o recarga el índice TF-IDF cuando el catálogo cambia."""
        from Backend.conexion_base import db
        with self._candado:
            firma = db.obtener_firma_catalogo_similitud()
            if self._firma == firma and self._embeddings is not None:
                return
            catalogo = db.cargar_catalogo_similitud()
            self._construir_embeddings(catalogo)
            self._firma = firma
    def _calcular_similitudes( self, documento_objetivo: str) -> np.ndarray:

        embedding_objetivo = self._modelo.encode(
            [documento_objetivo],
            normalize_embeddings=True
        )

        similitudes = cosine_similarity(
            embedding_objetivo,
            self._embeddings
        )

        return similitudes.flatten()

    # ------------------------------------------------------------------
    # Métodos privados — cálculo de similitudes
    # ------------------------------------------------------------------
    def _cargar_modelo(self) -> None:

        if self._modelo is None:
            self._modelo = SentenceTransformer(
                "sentence-transformers/all-MiniLM-L6-v2"
            )

   
    def _filtrar_y_ordenar(
        self,
        similitudes: np.ndarray,
        id_excluido: str | None,
        producto_objetivo: dict[str, Any] | None = None,
        estimacion_robusta: bool = False,
    ) -> list[tuple[float, dict[str, Any]]]:

        id_excluido_norm = (id_excluido or "").strip().upper()
        candidatos: list[tuple[float, dict[str, Any]]] = []
        
        atributos_objetivo = self._extraer_atributos_producto(producto_objetivo) if estimacion_robusta and producto_objetivo else {}
        similitud_maxima_local = float(np.max(similitudes)) if len(similitudes) > 0 else 0.0

        for indice, similitud in enumerate(similitudes):
            if similitud < _SIMILITUD_MINIMA:
                continue
                
            similitud_ajustada = float(similitud)
            producto = self._catalogo[indice]
            
            if estimacion_robusta:
                # Umbral relativo del 80% de la similitud máxima
                if similitud_ajustada < similitud_maxima_local * 0.80:
                    continue
                    
                # Penalización por discrepancia de atributos numéricos
                atributos_candidato = self._extraer_atributos_producto(producto)
                penalizar = False
                for clave, valor_obj in atributos_objetivo.items():
                    if clave in atributos_candidato:
                        valor_cand = atributos_candidato[clave]
                        if valor_obj > 0 and valor_cand > 0:
                            ratio = max(valor_obj, valor_cand) / min(valor_obj, valor_cand)
                            if ratio > 1.20:
                                penalizar = True
                                break
                if penalizar:
                    similitud_ajustada *= 0.50

            id_candidato = str(producto.get("id_producto") or "").strip().upper()
            if id_excluido_norm and id_candidato == id_excluido_norm:
                continue
            if producto.get("precio_actual") is None:
                continue
            candidatos.append((similitud_ajustada, producto))

        candidatos.sort(key=lambda par: par[0], reverse=True)
        return candidatos[:_LIMITE_SIMILARES]
    def _construir_embeddings(self,catalogo: list[dict[str, Any]]) -> None:

        self._cargar_modelo()

        documentos = [
            self._construir_documento(p)
            for p in catalogo
        ]

        self._embeddings = self._modelo.encode(
            documentos,
            normalize_embeddings=True
        )

        self._catalogo = catalogo

    # ------------------------------------------------------------------
    # Métodos privados — cálculo del precio
    # ------------------------------------------------------------------

    def _precio_ponderado(
        self,
        similares: list[tuple[float, dict[str, Any]]],
    ) -> float:
        suma_pesos = sum(sim ** 3 for sim, _ in similares)
        if suma_pesos <= 0:
            precios = [float(p["precio_actual"]) for _, p in similares]
            return float(np.mean(precios))
        suma_ponderada = sum(float(p["precio_actual"]) * (sim ** 3) for sim, p in similares)
        return suma_ponderada / suma_pesos

    # ------------------------------------------------------------------
    # Método público principal
    # ------------------------------------------------------------------

    def recomendar(
        self,
        nombre: str,
        marca: str | None = None,
        categoria: str | None = None,
        precio_actual: float | None = None,
        id_producto: str | None = None,
        estimacion_robusta: bool = True,
    ) -> dict[str, Any]:

        self._asegurar_indice()

        objetivo: dict[str, Any] = {
            "nombre": nombre,
            "marca": marca,
            "categoria": categoria,
        }
        documento = self._construir_documento(objetivo)
        similitudes = self._calcular_similitudes(documento)
        similares = self._filtrar_y_ordenar(similitudes, id_excluido=id_producto, producto_objetivo=objetivo, estimacion_robusta=estimacion_robusta)
        if categoria:

            similares = [
                (sim, prod)
                for sim, prod in similares
                if (
                    _normalizar_texto(prod.get("categoria"))
                    ==
                    _normalizar_texto(categoria)
                )
            ]

        # Advertencia cuando hay pocos similares
        advertencia: str | None = None
        if len(similares) < _MINIMO_ROBUSTO:
            advertencia = (
                f"Solo se encontraron {len(similares)} producto(s) similar(es) "
                f"(umbral >= {_SIMILITUD_MINIMA}). "
                "No existe suficiente información para generar una recomendación robusta."
            )

        if not similares:
            return {
                "precio_actual": precio_actual,
                "precio_recomendado": None,
                "cantidad_similares": 0,
                "similitud_promedio": None,
                "similitud_maxima": None,
                "producto_mas_similar": None,
                "productos_utilizados": [],
                "advertencia": advertencia,
            }

        precio_recomendado = self._precio_ponderado(similares)
        similitudes_valores = [sim for sim, _ in similares]

        similitud_maxima = float(max(similitudes_valores))
        similitud_promedio = float(np.mean(similitudes_valores))

        sim_max, prod_mas_similar = similares[0]
        producto_mas_similar = {
            "id_producto": prod_mas_similar.get("id_producto"),
            "nombre": prod_mas_similar.get("nombre"),
            "similitud": round(sim_max, 4),
        }

        productos_utilizados = [
            {
                "id_producto": p.get("id_producto"),
                "nombre": p.get("nombre"),
                "marca": p.get("marca"),
                "categoria": p.get("categoria"),
                "precio": float(p["precio_actual"]),
                "similitud": round(sim, 4),
            }
            for sim, p in similares
        ]

        return {
            "precio_actual": precio_actual,
            "precio_recomendado": round(precio_recomendado, 2),
            "cantidad_similares": len(similares),
            "similitud_promedio": round(similitud_promedio, 4),
            "similitud_maxima": round(similitud_maxima, 4),
            "producto_mas_similar": producto_mas_similar,
            "productos_utilizados": productos_utilizados,
            "advertencia": advertencia,
        }


# Instancia singleton para reutilizar el índice entre peticiones
_instancia: RecomendadorPrecio | None = None
_candado_singleton = threading.Lock()


def obtener_recomendador() -> RecomendadorPrecio:
    """Devuelve la instancia singleton de RecomendadorPrecio."""
    global _instancia
    if _instancia is None:
        with _candado_singleton:
            if _instancia is None:
                _instancia = RecomendadorPrecio()
    return _instancia
