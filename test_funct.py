import comtypes.client
from ctypes import c_double, POINTER, ARRAY

helper = comtypes.client.CreateObject("ETABSv1.Helper")
etabs_object = helper.GetObject("CSI.ETABS.API.ETABSObject")
sap_model = etabs_object.SapModel

func_th = sap_model.Func.FuncTH
lcid = 1033

print("=== Usando ctypes arrays ===\n")

# Opción 1: SetUserDefined con ctypes arrays
try:
    print("Intentando SetUserDefined con ctypes arrays...")
    
    # Crear arrays ctypes
    times = (c_double * 2)(0.0, 1.0)
    values = (c_double * 2)(0.0, 1.0)
    
    dispid = func_th.GetIDsOfNames(lcid, ("SetUserDefined",))[0]
    ret = func_th.Invoke(dispid, lcid, 1, ("MyTH", 2, times, values))
    
    print(f"  ✓ Retorno: {ret}")
except Exception as e:
    print(f"  ✗ Error: {type(e).__name__}: {e}")

# Opción 2: SetFromFile (debería ser más simple)
try:
    print("\nIntentando SetFromFile...")
    
    # Crear un archivo de prueba primero
    with open("C:\\temp\\test_th.txt", "w") as f:
        f.write("Time History Function\n")
        f.write("0.0 0.0\n")
        f.write("0.01 0.5\n")
        f.write("0.02 1.0\n")
        f.write("0.03 0.5\n")
        f.write("0.04 0.0\n")
    
    # Intentar cargar
    dispid = func_th.GetIDsOfNames(lcid, ("SetFromFile",))[0]
    ret = func_th.Invoke(dispid, lcid, 1, (
        "TestTH",
        "C:\\temp\\test_th.txt",
        0  # EqualIntervals
    ))
    
    print(f"  ✓ Retorno: {ret}")
except Exception as e:
    print(f"  ✗ Error: {type(e).__name__}: {e}")

# Opción 3: Intentar SetFromFile_1 (con underscore)
try:
    print("\nIntentando SetFromFile_1...")
    
    dispid = func_th.GetIDsOfNames(lcid, ("SetFromFile_1",))[0]
    ret = func_th.Invoke(dispid, lcid, 1, (
        "TestTH1",
        "C:\\temp\\test_th.txt",
        0,      # EqualIntervals
        0.01    # dt (si es equidistante)
    ))
    
    print(f"  ✓ Retorno: {ret}")
except Exception as e:
    print(f"  ✗ Error: {type(e).__name__}: {e}")

print("\n✓ Script completado")

# Verificar
ret_code, count, names = sap_model.Func.GetNameList(2)
print(f"\nFunciones time history creadas: {names if count > 0 else 'ninguna'}")
