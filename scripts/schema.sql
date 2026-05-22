-- DDL para la base de datos Oracle (Autonomous Database ATP)
-- Este script crea las tablas necesarias para almacenar productos y sus historiales de precios.

-- Opcional: Eliminar tablas existentes para recreación limpia en desarrollo
-- DROP TABLE historial_precios CASCADE CONSTRAINTS;
-- DROP TABLE productos CASCADE CONSTRAINTS;

-- Tabla PRODUCTOS (Datos Maestros del Producto)
CREATE TABLE productos (
    id_producto         VARCHAR2(20) NOT NULL,
    nombre              VARCHAR2(1000) NOT NULL,
    categoria           VARCHAR2(100),
    precio_actual       NUMBER(10, 2),
    fecha_actualizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT pk_productos PRIMARY KEY (id_producto),
    CONSTRAINT chk_precio_actual CHECK (precio_actual >= 0)
);

COMMENT ON TABLE productos IS 'Tabla maestra para almacenar la informacion de los productos escaneados de Amazon.';
COMMENT ON COLUMN productos.id_producto IS 'Identificador unico del producto (ASIN de Amazon).';
COMMENT ON COLUMN productos.nombre IS 'Nombre completo del producto.';
COMMENT ON COLUMN productos.categoria IS 'Categoria del producto.';
COMMENT ON COLUMN productos.precio_actual IS 'Ultimo precio registrado o actual del producto.';
COMMENT ON COLUMN productos.fecha_actualizacion IS 'Fecha y hora del ultimo cambio o insercion de datos del producto.';

-- Tabla HISTORIAL_PRECIOS (Registro Histórico Transaccional)
CREATE TABLE historial_precios (
    id_producto         VARCHAR2(20) NOT NULL,
    fecha               DATE NOT NULL,
    precio_registrado   NUMBER(10, 2) NOT NULL,
    CONSTRAINT pk_historial_precios PRIMARY KEY (id_producto, fecha),
    CONSTRAINT fk_historial_productos FOREIGN KEY (id_producto)
        REFERENCES productos (id_producto)
        ON DELETE CASCADE,
    CONSTRAINT chk_precio_registrado CHECK (precio_registrado >= 0)
);

COMMENT ON TABLE historial_precios IS 'Tabla que almacena la evolucion historica del precio por producto y por fecha.';
COMMENT ON COLUMN historial_precios.id_producto IS 'Identificador del producto (ASIN), llave foranea a productos.';
COMMENT ON COLUMN historial_precios.fecha IS 'Fecha del registro del precio.';
COMMENT ON COLUMN historial_precios.precio_registrado IS 'Precio del producto en la fecha especificada.';

-- Indices de rendimiento para consultas rapidas
CREATE INDEX idx_productos_cat ON productos(categoria);
CREATE INDEX idx_historial_fecha ON historial_precios(fecha);
