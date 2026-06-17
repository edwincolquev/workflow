WITH HistoricalLeadTime AS (
    SELECT
        T7.FirmName,
        AVG(DATEDIFF(day, T3.DocDate, T9.DocDate)) AS AvgHistoricalDays
    FROM POR1 T4
    INNER JOIN OPOR T3 
        ON T4.DocEntry = T3.DocEntry
    INNER JOIN OITM T8 
        ON T4.ItemCode = T8.ItemCode
    INNER JOIN OMRC T7 
        ON T8.FirmCode = T7.FirmCode
    INNER JOIN PCH1 T6
        ON T6.BaseType = 22
        AND T6.BaseEntry = T4.DocEntry
        AND T6.BaseLine = T4.LineNum
    INNER JOIN PDN1 T11
        ON T11.BaseType = 18
        AND T11.BaseEntry = T6.DocEntry
        AND T11.BaseLine = T6.LineNum
    INNER JOIN OPDN T9 
        ON T11.DocEntry = T9.DocEntry
    GROUP BY T7.FirmName
),
 
OC AS (
    SELECT
        T1.BaseEntry,
        T1.BaseLine,
        MIN(T0.TaxDate) AS FechaOC,
        SUM(T1.Quantity) AS CantidadOrdenada,
        SUM(T1.OpenQty) AS PendienteOC
    FROM POR1 T1
    INNER JOIN OPOR T0 
        ON T1.DocEntry = T0.DocEntry
    WHERE T0.CANCELED = 'N'
    GROUP BY 
        T1.BaseEntry, 
        T1.BaseLine
),
 
FACT AS (
    SELECT
        T3.BaseEntry,
        T3.BaseLine,
        MIN(T4.DocDate) AS FechaFactura,
        SUM(T5.Quantity) AS CantidadFacturada,
        SUM(T5.OpenQty) AS PendienteFaturar,
        MIN(T5.PriceBefDi) AS Precio
    FROM POR1 T3
    INNER JOIN PCH1 T5
        ON T5.BaseType = 22
        AND T5.BaseEntry = T3.DocEntry
        AND T5.BaseLine = T3.LineNum
    INNER JOIN OPCH T4 
        ON T5.DocEntry = T4.DocEntry
    WHERE T4.CANCELED = 'N'
    GROUP BY 
        T3.BaseEntry, 
        T3.BaseLine
),
 
ING AS (
    SELECT
        T3.BaseEntry,
        T3.BaseLine,
        MIN(T6.DocDate) AS FechaIngreso,
        SUM(T7.Quantity) AS CantidadIngresada
    FROM POR1 T3
    INNER JOIN PCH1 T5
        ON T5.BaseType = 22
        AND T5.BaseEntry = T3.DocEntry
        AND T5.BaseLine = T3.LineNum
    INNER JOIN PDN1 T7
        ON T7.BaseType = 18
        AND T7.BaseEntry = T5.DocEntry
        AND T7.BaseLine = T5.LineNum
    INNER JOIN OPDN T6 
        ON T7.DocEntry = T6.DocEntry
    WHERE T6.CANCELED = 'N'
    GROUP BY 
        T3.BaseEntry, 
        T3.BaseLine
),
 
BASE AS (
 
    SELECT
        T2.CardCode AS 'Código Proveedor',
        T2.CardName AS 'Nombre Proveedor',
        T7.FirmName AS 'Fabricante',
        T12.ItmsGrpNam AS 'Grupo Artículo',
 
        T0.DocNum,
        T0.NumAtCard AS 'Nombre Importacion (Oferta)',
 
        T1.ItemCode,
 
        T0.TaxDate AS 'Fecha Oferta Compra',
        OC.FechaOC AS 'Fecha Orden Compra',
        FACT.FechaFactura,
        ING.FechaIngreso,
 
        T8.LeadTime AS 'Lead Time Oferta',
 
        COALESCE(
            DATEDIFF(day, OC.FechaOC, ING.FechaIngreso),
            T10.AvgHistoricalDays,
            T8.LeadTime
        ) AS 'Lead Time Calc.',
 
        T1.Quantity AS 'Cantidad Ofertada',
        T1.OpenQty AS 'Cantidad Pendiente Ofertada',
 
        ISNULL(OC.CantidadOrdenada,0) AS 'Cantidad Ordenada',
        ISNULL(OC.PendienteOC,0) AS 'Pendiente OC',
 
        ISNULL(FACT.CantidadFacturada,0) AS 'Cantidad Facturada',
        ISNULL(FACT.PendienteFaturar,0) AS 'Pendiente FACT',
 
        ISNULL(ING.CantidadIngresada,0) AS 'Cantidad Ingresada',
 
        T1.OpenQty 
        + ISNULL(OC.PendienteOC,0) 
        + ISNULL(FACT.PendienteFaturar,0) AS 'En Transito',
 
        COALESCE(T1.Quantity, 0) 
        * COALESCE(T1.PriceBefDi, 0) AS 'Monto Ofertado USD',
 
        COALESCE(T1.OpenQty, 0) 
        * COALESCE(T1.PriceBefDi, 0) AS 'Monto Pendiente Ofertado USD',
 
        COALESCE(FACT.CantidadFacturada,0) 
        * COALESCE(FACT.Precio, 0) AS 'Monto Facturado',
 
        -- =========================================
        -- FECHA ESTIMADA BASE
        -- =========================================
 
        CASE
            WHEN OC.FechaOC IS NOT NULL THEN
 
                DATEADD(
                    day,
                    COALESCE(
                        DATEDIFF(day, OC.FechaOC, ING.FechaIngreso),
                        T10.AvgHistoricalDays,
                        T8.LeadTime
                    ),
                    OC.FechaOC
                )
 
            ELSE
                DATEADD(
                    day,
                    T8.LeadTime,
                    T0.TaxDate
                )
        END AS FechaEstimadaBase
 
    FROM PQT1 T1
 
    INNER JOIN OPQT T0 
        ON T1.DocEntry = T0.DocEntry
 
    INNER JOIN OCRD T2 
        ON T0.CardCode = T2.CardCode
 
    INNER JOIN OITM T8 
        ON T1.ItemCode = T8.ItemCode
 
    LEFT JOIN OMRC T7 
        ON T8.FirmCode = T7.FirmCode
 
    LEFT JOIN OC
        ON OC.BaseEntry = T1.DocEntry
        AND OC.BaseLine = T1.LineNum
 
    LEFT JOIN FACT
        ON FACT.BaseEntry = T1.DocEntry
        AND FACT.BaseLine = T1.LineNum
 
    LEFT JOIN ING
        ON ING.BaseEntry = T1.DocEntry
        AND ING.BaseLine = T1.LineNum
 
    LEFT JOIN HistoricalLeadTime T10
        ON T7.FirmName = T10.FirmName
 
    LEFT JOIN OITB T12
        ON T8.ItmsGrpCod = T12.ItmsGrpCod
 
    WHERE
        T0.CANCELED = 'N'
)
 
SELECT
    *,
 
    -- =========================================
    -- DIAS DE RETRASO
    -- =========================================
 
    DATEDIFF(
        day,
        FechaEstimadaBase,
        GETDATE()
    ) AS DiasRetraso,
 
    -- =========================================
    -- ESTADO FLUJO
    -- =========================================
    -- SOLO DEFINE SI ESTA ACTIVO O COMPLETADO
 
    CASE
        WHEN
            ISNULL([Cantidad Pendiente Ofertada],0) <= 0
            AND ISNULL([Pendiente OC],0) <= 0
            AND ISNULL([Pendiente FACT],0) <= 0
        THEN 'Completado'
 
        ELSE 'Pendiente'
 
    END AS EstadoFlujo,
 
    -- =========================================
    -- ESTADO RETRASO
    -- =========================================
 
    CASE
 
        WHEN
            ISNULL([Cantidad Pendiente Ofertada],0) <= 0
            AND ISNULL([Pendiente OC],0) <= 0
            AND ISNULL([Pendiente FACT],0) <= 0
        THEN 'Completado'
 
        WHEN DATEDIFF(day, FechaEstimadaBase, GETDATE()) > 0
        THEN 'Retrasado'
 
        ELSE 'En Tiempo'
 
    END AS EstadoRetraso,
 
    -- =========================================
    -- FECHA ESTIMADA FINAL AJUSTADA
    -- =========================================
 
    CASE
 
        -- COMPLETADO
        WHEN
            ISNULL([Cantidad Pendiente Ofertada],0) <= 0
            AND ISNULL([Pendiente OC],0) <= 0
            AND ISNULL([Pendiente FACT],0) <= 0
        THEN
            FechaIngreso
 
        -- TIENE OC Y ESTA RETRASADO
        WHEN [Fecha Orden Compra] IS NOT NULL
             AND DATEDIFF(day, FechaEstimadaBase, GETDATE()) > 0
        THEN
            DATEADD(
                day,
                10,
                CONVERT(date, GETDATE())
            )
 
        -- SOLO OFERTA Y ESTA RETRASADO
        WHEN [Fecha Orden Compra] IS NULL
             AND DATEDIFF(day, FechaEstimadaBase, GETDATE()) > 0
        THEN
            DATEADD(
                day,
                [Lead Time Calc.],
                CONVERT(date, GETDATE())
            )
 
        -- SIN RETRASO
        ELSE
            FechaEstimadaBase
 
    END AS 'Fecha Estimada de Llegada',
 
    -- =========================================
    -- ETAPA FUNCIONAL
    -- =========================================
 
    CASE
 
        -- COMPLETADO
        WHEN
            ISNULL([Cantidad Pendiente Ofertada],0) <= 0
            AND ISNULL([Pendiente OC],0) <= 0
            AND ISNULL([Pendiente FACT],0) <= 0
        THEN 'Completado'
 
        -- SIN OC
        WHEN [Fecha Orden Compra] IS NULL
        THEN 'Pendiente OC'
 
        -- CON OC SIN FACTURA
        WHEN FechaFactura IS NULL
        THEN 'En Producción'
 
        -- FACTURADO Y RETRASADO
        WHEN FechaFactura IS NOT NULL
             AND (
                    ISNULL([Pendiente FACT],0) > 0
                    OR ISNULL([En Transito],0) > 0
                 )
             AND DATEDIFF(day, FechaEstimadaBase, GETDATE()) > 0
        THEN 'En Tránsito Retrasado'
 
        -- FACTURADO EN TRANSITO
        WHEN FechaFactura IS NOT NULL
             AND (
                    ISNULL([Pendiente FACT],0) > 0
                    OR ISNULL([En Transito],0) > 0
                 )
        THEN 'En Tránsito'
 
        ELSE 'Revisar'
 
    END AS Etapa
 
FROM BASE
 
ORDER BY
    [Nombre Proveedor],
    Fabricante,
    [Fecha Oferta Compra]
