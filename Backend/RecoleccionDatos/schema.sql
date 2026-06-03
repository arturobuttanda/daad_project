-- DDL para la base de datos Oracle (Autonomous Database ATP)
-- Este script crea las tablas necesarias para almacenar productos y sus historiales de precios.

-- Opcional: Eliminar tablas existentes para recreación limpia en desarrollo
-- DROP TABLE historial_precios CASCADE CONSTRAINTS;
-- DROP TABLE productos CASCADE CONSTRAINTS;

BEGIN
    EXECUTE IMMEDIATE 'DROP TABLE historial_precios CASCADE CONSTRAINTS';
EXCEPTION
    WHEN OTHERS THEN
        IF SQLCODE != -942 THEN
            RAISE;
        END IF;
END;
/

BEGIN
    EXECUTE IMMEDIATE 'DROP TABLE productos CASCADE CONSTRAINTS';
EXCEPTION
    WHEN OTHERS THEN
        IF SQLCODE != -942 THEN
            RAISE;
        END IF;
END;
/

BEGIN
    EXECUTE IMMEDIATE 'DROP TABLE venta_detalle CASCADE CONSTRAINTS';
EXCEPTION
    WHEN OTHERS THEN
        IF SQLCODE != -942 THEN
            RAISE;
        END IF;
END;
/ 

BEGIN
    EXECUTE IMMEDIATE 'DROP TABLE ventas CASCADE CONSTRAINTS';
EXCEPTION
    WHEN OTHERS THEN
        IF SQLCODE != -942 THEN
            RAISE;
        END IF;
END;
/ 

BEGIN
    EXECUTE IMMEDIATE 'DROP TABLE competencia_mercado CASCADE CONSTRAINTS';
EXCEPTION
    WHEN OTHERS THEN
        IF SQLCODE != -942 THEN
            RAISE;
        END IF;
END;
/ 

BEGIN
    EXECUTE IMMEDIATE 'DROP TABLE producto_vendedor CASCADE CONSTRAINTS';
EXCEPTION
    WHEN OTHERS THEN
        IF SQLCODE != -942 THEN
            RAISE;
        END IF;
END;
/ 

BEGIN
    EXECUTE IMMEDIATE 'DROP TABLE vendedores CASCADE CONSTRAINTS';
EXCEPTION
    WHEN OTHERS THEN
        IF SQLCODE != -942 THEN
            RAISE;
        END IF;
END;
/ 

-- Tabla PRODUCTOS (Datos Maestros del Producto)
CREATE TABLE productos (
    id_producto         VARCHAR2(20) NOT NULL,
    nombre              VARCHAR2(1000) NOT NULL,
    marca               VARCHAR2(150),
    categoria           VARCHAR2(100),
    precio_actual       NUMBER(10, 2),
    stock               NUMBER(10) DEFAULT 0 NOT NULL,
    precio_fabricacion  NUMBER(10, 2),
    fecha_caducidad     DATE,
    imagen_url          CLOB,
    fecha_actualizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT pk_productos PRIMARY KEY (id_producto),
    CONSTRAINT chk_precio_actual CHECK (precio_actual >= 0)
    ,CONSTRAINT chk_stock CHECK (stock >= 0)
    ,CONSTRAINT chk_precio_fabricacion CHECK (precio_fabricacion >= 0)
);

COMMENT ON TABLE productos IS 'Tabla maestra para almacenar la informacion de los productos escaneados de Amazon.';
COMMENT ON COLUMN productos.id_producto IS 'Identificador unico del producto (ASIN de Amazon).';
COMMENT ON COLUMN productos.nombre IS 'Nombre completo del producto.';
COMMENT ON COLUMN productos.marca IS 'Marca o fabricante del producto.';
COMMENT ON COLUMN productos.categoria IS 'Categoria del producto.';
COMMENT ON COLUMN productos.precio_actual IS 'Ultimo precio registrado o actual del producto.';
COMMENT ON COLUMN productos.stock IS 'Cantidad disponible en inventario.';
COMMENT ON COLUMN productos.precio_fabricacion IS 'Costo interno o precio de fabricacion.';
COMMENT ON COLUMN productos.fecha_caducidad IS 'Fecha de caducidad del producto si aplica.';
COMMENT ON COLUMN productos.imagen_url IS 'URL de la imagen del producto o data URL base64.';
COMMENT ON COLUMN productos.fecha_actualizacion IS 'Fecha y hora del ultimo cambio o insercion de datos del producto.';

BEGIN
    EXECUTE IMMEDIATE 'ALTER TABLE productos ADD (marca VARCHAR2(150))';
EXCEPTION
    WHEN OTHERS THEN
        IF SQLCODE != -1430 THEN
            RAISE;
        END IF;
END;

BEGIN
    EXECUTE IMMEDIATE 'ALTER TABLE productos ADD (imagen_url CLOB)';
EXCEPTION
    WHEN OTHERS THEN
        IF SQLCODE != -1430 THEN
            RAISE;
        END IF;
END;
/
/ 

BEGIN
    EXECUTE IMMEDIATE 'ALTER TABLE productos ADD (stock NUMBER(10) DEFAULT 0 NOT NULL)';
EXCEPTION
    WHEN OTHERS THEN
        IF SQLCODE != -1430 THEN
            RAISE;
        END IF;
END;
/ 

BEGIN
    EXECUTE IMMEDIATE 'ALTER TABLE productos ADD (precio_fabricacion NUMBER(10, 2))';
EXCEPTION
    WHEN OTHERS THEN
        IF SQLCODE != -1430 THEN
            RAISE;
        END IF;
END;
/ 

BEGIN
    EXECUTE IMMEDIATE 'ALTER TABLE productos ADD (fecha_caducidad DATE)';
EXCEPTION
    WHEN OTHERS THEN
        IF SQLCODE != -1430 THEN
            RAISE;
        END IF;
END;
/ 

-- Tabla HISTORIAL_PRECIOS (Registro Historico Transaccional)
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
BEGIN
    EXECUTE IMMEDIATE 'DROP INDEX idx_historial_fecha';
EXCEPTION
    WHEN OTHERS THEN
        IF SQLCODE != -1418 THEN
            RAISE;
        END IF;
END;
/

CREATE INDEX idx_historial_fecha ON historial_precios(fecha);

-- Indices de rendimiento para consultas rapidas
BEGIN
    EXECUTE IMMEDIATE 'DROP INDEX idx_productos_cat';
EXCEPTION
    WHEN OTHERS THEN
        IF SQLCODE != -1418 THEN
            RAISE;
        END IF;
END;
/

CREATE INDEX idx_productos_cat ON productos(categoria);

-- Tabla USUARIOS (Autenticacion y registro)
BEGIN
    EXECUTE IMMEDIATE 'DROP TABLE usuarios CASCADE CONSTRAINTS';
EXCEPTION
    WHEN OTHERS THEN
        IF SQLCODE != -942 THEN
            RAISE;
        END IF;
END;
/

CREATE TABLE usuarios (
    id_usuario      VARCHAR2(36) NOT NULL,
    nombre          VARCHAR2(150) NOT NULL,
    telefono        VARCHAR2(30),
    correo          VARCHAR2(150) NOT NULL,
    tipo_usuario    VARCHAR2(20) NOT NULL,
    password_hash   VARCHAR2(255) NOT NULL,
    fecha_creacion  TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT pk_usuarios PRIMARY KEY (id_usuario),
    CONSTRAINT uq_usuarios_correo UNIQUE (correo),
    CONSTRAINT chk_usuarios_tipo CHECK (tipo_usuario IN ('Vendedor', 'Cliente'))
);

COMMENT ON TABLE usuarios IS 'Tabla para registro y autenticacion de usuarios.';
COMMENT ON COLUMN usuarios.correo IS 'Correo unico del usuario.';
COMMENT ON COLUMN usuarios.tipo_usuario IS 'Tipo de usuario: Vendedor o Cliente.';

BEGIN
    EXECUTE IMMEDIATE 'DROP INDEX idx_usuarios_tipo';
EXCEPTION
    WHEN OTHERS THEN
        IF SQLCODE != -1418 THEN
            RAISE;
        END IF;
END;
/

CREATE INDEX idx_usuarios_tipo ON usuarios(tipo_usuario);

-- Tabla VENDEDORES (perfil operativo del usuario vendedor)
CREATE TABLE vendedores (
    id_vendedor         VARCHAR2(36) NOT NULL,
    codigo_vendedor     VARCHAR2(20) NOT NULL,
    especialidad        VARCHAR2(120),
    objetivo_ventas     NUMBER(10, 2) DEFAULT 0,
    fecha_alta          TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT pk_vendedores PRIMARY KEY (id_vendedor),
    CONSTRAINT uq_vendedores_codigo UNIQUE (codigo_vendedor),
    CONSTRAINT fk_vendedores_usuario FOREIGN KEY (id_vendedor)
        REFERENCES usuarios (id_usuario)
        ON DELETE CASCADE
);

COMMENT ON TABLE vendedores IS 'Perfil extendido para usuarios tipo vendedor.';

-- Distribucion de productos por vendedor
CREATE TABLE producto_vendedor (
    id_producto         VARCHAR2(20) NOT NULL,
    id_vendedor         VARCHAR2(36) NOT NULL,
    fecha_asignacion     TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT pk_producto_vendedor PRIMARY KEY (id_producto),
    CONSTRAINT fk_pv_producto FOREIGN KEY (id_producto)
        REFERENCES productos (id_producto)
        ON DELETE CASCADE,
    CONSTRAINT fk_pv_vendedor FOREIGN KEY (id_vendedor)
        REFERENCES vendedores (id_vendedor)
        ON DELETE CASCADE
);

CREATE INDEX idx_producto_vendedor_vendedor ON producto_vendedor(id_vendedor);

-- Señales de competencia para recomendaciones de venta
CREATE TABLE competencia_mercado (
    id_competencia              NUMBER GENERATED BY DEFAULT AS IDENTITY,
    id_producto                 VARCHAR2(20) NOT NULL,
    fecha                       DATE DEFAULT CURRENT_DATE NOT NULL,
    precio_competencia_promedio  NUMBER(10, 2) NOT NULL,
    fuente                      VARCHAR2(150),
    CONSTRAINT pk_competencia_mercado PRIMARY KEY (id_competencia),
    CONSTRAINT fk_competencia_producto FOREIGN KEY (id_producto)
        REFERENCES productos (id_producto)
        ON DELETE CASCADE,
    CONSTRAINT chk_competencia_precio CHECK (precio_competencia_promedio >= 0)
);

CREATE INDEX idx_competencia_producto_fecha ON competencia_mercado(id_producto, fecha DESC);

-- Cabecera de ventas, sirve como ticket de venta
CREATE TABLE ventas (
    id_venta        VARCHAR2(36) NOT NULL,
    id_cliente      VARCHAR2(36) NOT NULL,
    id_vendedor     VARCHAR2(36),
    fecha_venta     TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    monto_total     NUMBER(12, 2) NOT NULL,
    total_unidades  NUMBER(10) NOT NULL,
    CONSTRAINT pk_ventas PRIMARY KEY (id_venta),
    CONSTRAINT fk_ventas_cliente FOREIGN KEY (id_cliente)
        REFERENCES usuarios (id_usuario),
    CONSTRAINT fk_ventas_vendedor FOREIGN KEY (id_vendedor)
        REFERENCES vendedores (id_vendedor)
        ON DELETE SET NULL,
    CONSTRAINT chk_ventas_monto CHECK (monto_total >= 0),
    CONSTRAINT chk_ventas_unidades CHECK (total_unidades >= 0)
);

CREATE INDEX idx_ventas_cliente_fecha ON ventas(id_cliente, fecha_venta DESC);

-- Detalle de la venta por producto
CREATE TABLE venta_detalle (
    id_venta         VARCHAR2(36) NOT NULL,
    id_producto      VARCHAR2(20) NOT NULL,
    cantidad         NUMBER(10) NOT NULL,
    precio_unitario  NUMBER(10, 2) NOT NULL,
    costo_unitario   NUMBER(10, 2),
    subtotal         NUMBER(12, 2) NOT NULL,
    margen_unitario  NUMBER(10, 2),
    CONSTRAINT pk_venta_detalle PRIMARY KEY (id_venta, id_producto),
    CONSTRAINT fk_detalle_venta FOREIGN KEY (id_venta)
        REFERENCES ventas (id_venta)
        ON DELETE CASCADE,
    CONSTRAINT fk_detalle_producto FOREIGN KEY (id_producto)
        REFERENCES productos (id_producto),
    CONSTRAINT chk_detalle_cantidad CHECK (cantidad > 0),
    CONSTRAINT chk_detalle_precio CHECK (precio_unitario >= 0),
    CONSTRAINT chk_detalle_subtotal CHECK (subtotal >= 0)
);

CREATE INDEX idx_venta_detalle_producto ON venta_detalle(id_producto);
