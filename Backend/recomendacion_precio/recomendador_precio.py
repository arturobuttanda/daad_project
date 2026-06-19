from __future__ import annotations

"""Recomendador de precios basado en TF-IDF + Similitud Coseno.

Implementa la clase RecomendadorPrecio que encapsula toda la lógica
matemática de búsqueda de productos similares y cálculo de precio
ponderado usando aprendizaje automático clásico.

Arquitectura:
    Frontend → FastAPI → RecomendadorPrecio → Oracle

La lógica matemática reside únicamente en este módulo.
"""

from typing import Any
import unicodedata
import threading
import logging

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from sentence_transformers import SentenceTransformer


bitacora = logging.getLogger("daad-backend")

# Umbral mínimo de similitud coseno para incluir un producto
_SIMILITUD_MINIMA: float = 0.10

# Cantidad máxima de productos similares a considerar
_LIMITE_SIMILARES: int = 10

# Mínimo de similares para una recomendación robusta
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
    """Servicio de recomendación de precios por similitud semántica TF-IDF.

    Construye una matriz TF-IDF sobre el catálogo de productos de Oracle y
    calcula la similitud coseno entre el producto objetivo y todos los demás.
    El precio recomendado se obtiene como promedio ponderado por similitud.

    Uso:
        recomendador = RecomendadorPrecio()
        resultado = recomendador.recomendar(
            id_producto="PROD-001",
            nombre="Television TCL",
            marca="TCL",
            categoria="Electronica",
            precio_actual=15000.0,
        )

    El resultado es un diccionario con precio_recomendado y métricas de
    similitud. La instancia se puede reutilizar; el catálogo se recarga
    automáticamente cuando la firma cambia.
    """

    def __init__(self) -> None:
        self._modelo: SentenceTransformer | None = None
        self._embeddings: np.ndarray | None = None       
        self._catalogo: list[dict[str, Any]] = []
        self._firma: tuple[int, str] | None = None
        self._candado = threading.Lock()

    # ------------------------------------------------------------------
    # Métodos privados — construcción del índice
    # ------------------------------------------------------------------

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
            catalogo = db.cargar_catalogo_similitud(firma)
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
    ) -> list[dict[str, Any]]:
        """Filtra productos por umbral de similitud y los ordena descendente.

        Excluye el producto consultado (self), aplica el umbral mínimo y
        limita a _LIMITE_SIMILARES productos.
        """
        id_excluido_norm = (id_excluido or "").strip().upper()
        candidatos: list[tuple[float, dict[str, Any]]] = []

        for indice, similitud in enumerate(similitudes):
            if similitud < _SIMILITUD_MINIMA:
                continue
            producto = self._catalogo[indice]
            id_candidato = str(producto.get("id_producto") or "").strip().upper()
            if id_excluido_norm and id_candidato == id_excluido_norm:
                continue
            if producto.get("precio_actual") is None:
                continue
            candidatos.append((float(similitud), producto))

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
        """Calcula el precio recomendado como promedio ponderado por similitud.

        Fórmula:
            precio_recomendado = Σ(precio_i × similitud_i) / Σ(similitud_i)

        Los productos con mayor similitud coseno tienen mayor peso, por lo
        que el precio resultante se acerca más a los productos más parecidos.
        """
        suma_pesos = sum(sim for sim, _ in similares)
        if suma_pesos <= 0:
            precios = [float(p["precio_actual"]) for _, p in similares]
            return float(np.mean(precios))

        suma_ponderada = sum(
            float(p["precio_actual"]) * sim for sim, p in similares
        )
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
    ) -> dict[str, Any]:
        """Genera una recomendación de precio para el producto dado.

        Parámetros:
            nombre: Nombre del producto (obligatorio).
            marca: Marca del producto (opcional).
            categoria: Categoría del producto (opcional).
            precio_actual: Precio actual del producto (para incluirlo en la respuesta).
            id_producto: ID del producto a excluir del catálogo (evita auto-similitud).

        Retorna:
            Diccionario con precio_recomendado, métricas de similitud y la
            lista de productos utilizados en el cálculo.
        """
        self._asegurar_indice()

        objetivo: dict[str, Any] = {
            "nombre": nombre,
            "marca": marca,
            "categoria": categoria,
        }
        documento = self._construir_documento(objetivo)
        similitudes = self._calcular_similitudes(documento)
        similares = self._filtrar_y_ordenar(similitudes, id_excluido=id_producto)
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
