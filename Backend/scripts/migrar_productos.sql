-- =============================================================================
-- Migración: Eliminar fecha_actualizacion y fecha_caducidad de productos
-- =============================================================================

-- 1. Respaldar datos actuales
CREATE TABLE productos_backup AS SELECT * FROM productos;

-- 2. Crear tabla nueva con las columnas definitivas
CREATE TABLE productos_nueva AS
SELECT id_producto, nombre, categoria, marca, precio_actual, stock, precio_fabricacion, imagen_url
FROM productos;

-- 3. Eliminar constraints de tablas hijas
ALTER TABLE producto_vendedor DROP CONSTRAINT fk_pv_producto;
ALTER TABLE venta_detalle DROP CONSTRAINT fk_detalle_producto;
ALTER TABLE historial_precios DROP CONSTRAINT fk_historial_productos;
ALTER TABLE competencia_mercado DROP CONSTRAINT fk_competencia_producto;

-- 4. Eliminar tabla vieja
DROP TABLE productos CASCADE CONSTRAINTS;

-- 5. Renombrar tabla nueva
ALTER TABLE productos_nueva RENAME TO productos;

-- 6. Recrear constraints
ALTER TABLE productos ADD CONSTRAINT pk_productos PRIMARY KEY (id_producto);
ALTER TABLE productos ADD CONSTRAINT chk_precio_actual CHECK (precio_actual >= 0);
ALTER TABLE productos ADD CONSTRAINT chk_stock CHECK (stock >= 0);
ALTER TABLE productos ADD CONSTRAINT chk_precio_fabricacion CHECK (precio_fabricacion >= 0);

-- 7. Recrear FK de tablas hijas
ALTER TABLE producto_vendedor ADD CONSTRAINT fk_pv_producto
  FOREIGN KEY (id_producto) REFERENCES productos(id_producto) ON DELETE CASCADE;
ALTER TABLE venta_detalle ADD CONSTRAINT fk_detalle_producto
  FOREIGN KEY (id_producto) REFERENCES productos(id_producto);
ALTER TABLE historial_precios ADD CONSTRAINT fk_historial_productos
  FOREIGN KEY (id_producto) REFERENCES productos(id_producto) ON DELETE CASCADE;
ALTER TABLE competencia_mercado ADD CONSTRAINT fk_competencia_producto
  FOREIGN KEY (id_producto) REFERENCES productos(id_producto) ON DELETE CASCADE;

-- 8. Recrear índices
CREATE INDEX idx_productos_cat ON productos(categoria);

-- 9. Comentarios
COMMENT ON TABLE productos IS 'Tabla maestra para almacenar la informacion de los productos del sistema.';
COMMENT ON COLUMN productos.id_producto IS 'Identificador unico del producto.';
COMMENT ON COLUMN productos.nombre IS 'Nombre completo del producto.';
COMMENT ON COLUMN productos.marca IS 'Marca o fabricante del producto.';
COMMENT ON COLUMN productos.categoria IS 'Categoria del producto.';
COMMENT ON COLUMN productos.precio_actual IS 'Precio de venta actual del producto.';
COMMENT ON COLUMN productos.stock IS 'Cantidad disponible en inventario.';
COMMENT ON COLUMN productos.precio_fabricacion IS 'Costo interno o precio de fabricacion.';
COMMENT ON COLUMN productos.imagen_url IS 'URL o identificador de la imagen del producto.';
