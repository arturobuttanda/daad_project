from datetime import date
from typing import List, Optional

class Persona:
    """Clase abstracta que define la estructura base de un usuario."""
    def __init__(self, 
                 id_persona: str, 
                 nombre: str, 
                 telefono: str, 
                 correo: str, 
                 tipo_usuario: str):
        if type(self) == Persona:
            raise TypeError("No se puede instanciar la clase abstracta Persona directamente.")
        self.id = id_persona
        self.nombre = nombre
        self.telefono = telefono
        self.correo = correo
        self.tipo_usuario = tipo_usuario 


class Producto:
    """Contenedor de datos de los productos."""
    def __init__(self, 
                 id_producto: str, 
                 nombre_producto: str, 
                 marca: str, 
                 precio_venta_actual: float, 
                 stock: int, 
                 precio_fabricacion: float, 
                 fecha_caducidad: Optional[date] = None):
        self.id_producto = id_producto
        self.nombre_producto = nombre_producto
        self.marca = marca
        self.precio_venta_actual = precio_venta_actual
        self.stock = stock
        self.fecha_caducidad = fecha_caducidad
        # Atributo privado/encapsulado para proteger el costo de fabricación
        self._precio_fabricacion = precio_fabricacion


class Venta:
    """Registro individual de una transacción comercial."""
    def __init__(self, 
                 id_venta: str, 
                 producto: Producto, 
                 cantidad: int, 
                 fecha_venta: date,
                 total_pagado: float):
        self.id_venta = id_venta
        self.producto = producto
        self.cantidad = cantidad
        self.fecha_venta = fecha_venta
        self.total_pagado = total_pagado


class Informe:
    """Estructura de salida para el balance financiero."""
    def __init__(self,
                  ingresos_totales: float, 
                  costos_totales: float, 
                  margen_ganancia: float, 
                  alertas_stock_bajo: List[Producto]):
        self.ingresos_totales = ingresos_totales
        self.costos_totales = costos_totales
        self.margen_ganancia = margen_ganancia
        self.alertas_stock_bajo = alertas_stock_bajo


class Cliente(Persona):
    """Rol de consumidor. Interactúa con productos sin acceder a costos internos."""
    def __init__(self, id_persona: str, nombre: str, telefono: str, correo: str, 
                 presupuesto_maximo: float):
        super().__init__(id_persona, nombre, telefono, correo, tipo_usuario="Cliente")
        self.historial_compras: List[Venta] = []
        self.presupuesto_maximo = presupuesto_maximo

    def consultar_precio_mas_bajo(self, p: Producto) -> float:
        # TODO: Implementar filtro IQR para quitar outliers exagerados
        pass

    def hacer_analisis_precio(self, p: Producto) -> str:
        # TODO: Comparar con promedio histórico y estimar tiempo de espera
        pass

    def recomendacion_compra(self, p: Producto) -> str:
        # TODO: Predecir cuándo el precio estará por debajo del promedio
        pass

    def registrar_compra(self, v: Venta) -> None:
        # TODO: Añadir la venta al historial compras
        pass


class Vendedor(Persona):
    """Rol operativo. Administra el inventario y accede a las finanzas internas."""
    def __init__(self, id_persona: str, nombre: str, telefono: str, correo: str, 
                 id_vendedor: str):
        super().__init__(id_persona, nombre, telefono, correo, tipo_usuario="Vendedor")
        self.id_vendedor = id_vendedor
        self.productos_asignados: List[Producto] = []

    def obtener_costo_fabricacion(self, p: Producto) -> float:
        """Acceso exclusivo al costo oculto del producto."""
        return p._precio_fabricacion

    def vender_producto(self, p: Producto, q: int) -> Venta:
        # TODO: Descontar stock y retornar objeto Venta
        pass

    def recomendacion_de_precio(self, p: Producto) -> float:
        # TODO: Integrar lógica de IA y comparación de mercado externo
        pass

    def ajustar_precio(self, p: Producto, porcentaje: float) -> None:
        # TODO: Modificar precio_venta_actual (ej. 0.05 para +5%) y emitir alertas estacionales
        pass

    def quitar_producto(self, p: Producto) -> None:
        # TODO: Remover producto de la lista de asignados
        pass

    def generar_informe_financiero(self) -> Informe:
        # TODO: Calcular ingresos, costos totales y retornar objeto Informe
        pass

    def checar_inventario(self) -> List[Producto]:
        # TODO: Retornar estados de stock y validar fechas de caducidad
        pass