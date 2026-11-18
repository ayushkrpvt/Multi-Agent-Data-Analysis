-- Northwind schema (SQLite), generated from database/northwind.db
CREATE TABLE IF NOT EXISTS "categories" (
"CategoryID" INTEGER,
  "CategoryName" TEXT,
  "Description" TEXT
);
CREATE TABLE IF NOT EXISTS "customers" (
"CustomerID" TEXT,
  "CompanyName" TEXT,
  "ContactName" TEXT,
  "ContactTitle" TEXT,
  "Address" TEXT,
  "City" TEXT,
  "Region" TEXT,
  "PostalCode" TEXT,
  "Country" TEXT,
  "Phone" TEXT,
  "Fax" TEXT
);
CREATE TABLE IF NOT EXISTS "employee_territory" (
"EmployeeID" INTEGER,
  "TerritoryID" INTEGER
);
CREATE TABLE IF NOT EXISTS "employees" (
"EmployeeID" INTEGER,
  "LastName" TEXT,
  "FirstName" TEXT,
  "Title" TEXT,
  "TitleOfCourtesy" TEXT,
  "BirthDate" TEXT,
  "HireDate" TEXT,
  "Address" TEXT,
  "City" TEXT,
  "Region" TEXT,
  "Country" TEXT,
  "HomePhone" TEXT,
  "Salary" REAL,
  "Unnamed: 13" TEXT
);
CREATE TABLE IF NOT EXISTS "order_details" (
"OrderID" INTEGER,
  "ProductID" INTEGER,
  "UnitPrice" REAL,
  "Quantity" INTEGER,
  "Discount" INTEGER
);
CREATE TABLE IF NOT EXISTS "orders" (
"OrderID" INTEGER,
  "CustomerID" TEXT,
  "EmployeeID" INTEGER,
  "OrderDate" TEXT,
  "RequiredDate" TEXT,
  "ShippedDate" TEXT,
  "ShipVia" INTEGER,
  "Freight" REAL,
  "ShipName" TEXT,
  "ShipAddress" TEXT,
  "ShipCity" TEXT,
  "ShipRegion" TEXT,
  "ShipPostalCode" TEXT,
  "ShipCountry" TEXT
);
CREATE TABLE IF NOT EXISTS "products" (
"ProductID" INTEGER,
  "ProductName" TEXT,
  "SupplierID" INTEGER,
  "CategoryID" INTEGER,
  "QuantityPerUnit" TEXT,
  "UnitPrice" REAL,
  "UnitsInStock" INTEGER,
  "UnitsOnOrder" INTEGER,
  "ReorderLevel" INTEGER,
  "Discontinued" INTEGER
);
CREATE TABLE IF NOT EXISTS "region" (
"RegionID" INTEGER,
  "RegionDescription" TEXT
);
CREATE TABLE IF NOT EXISTS "shippers" (
"ShipperID" INTEGER,
  "CompanyName" TEXT,
  "Phone" TEXT
);
CREATE TABLE IF NOT EXISTS "suppliers" (
"SupplierID" INTEGER,
  "CompanyName" TEXT,
  "ContactName" TEXT,
  "ContactTitle" TEXT,
  "Address" TEXT,
  "City" TEXT,
  "Region" TEXT,
  "PostalCode" TEXT,
  "Country" TEXT,
  "Phone" TEXT,
  "Fax" TEXT,
  "HomePage" TEXT
);
CREATE TABLE IF NOT EXISTS "territories" (
"TerritoryID" INTEGER,
  "TerritoryDescription" TEXT,
  "RegionID" INTEGER
);
