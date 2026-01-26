"""
SAP2000 v26 - Cargar Acelerograma
Basado en documentación oficial SetFromFile_1
"""

import comtypes.client
import os

def connect_to_sap2000():
    """Conecta a instancia abierta de SAP2000"""
    try:
        print("Conectando a SAP2000...")
        helper = comtypes.client.CreateObject("SAP2000v1.Helper")
        sap_object = helper.GetObject("CSI.SAP2000.API.SapObject")
        sap_model = sap_object.SapModel
        print("✓ Conectado a SAP2000\n")
        return sap_object, sap_model
    except Exception as e:
        print(f"✗ Error: No se pudo conectar a SAP2000")
        print(f"   Asegúrate de que SAP2000 esté abierto con un modelo")
        raise

def load_accelerogram(sap_model, name, filepath, headLines=3, dt=0.005):
    """
    Carga un acelerograma desde archivo
    
    SetFromFile_1(Name, FileName, HeadLines, PreChars, PointsPerLine, ValueType, 
                  FreeFormat, NumberFixed, DT)
    
    Para archivo con formato:
    - 3 líneas header
    - 1 columna de datos (valores a intervalos iguales)
    - dt = 0.005 segundos
    """
    
    print(f"Cargando acelerograma '{name}'...")
    print(f"  Archivo: {filepath}")
    print(f"  HeadLines: {headLines}, DT: {dt}\n")
    
    if not os.path.exists(filepath):
        print(f"✗ Archivo no encontrado: {filepath}")
        return -1
    
    try:
        func_th = sap_model.Func.FuncTH
        
        # Parámetros según documentación SAP2000:
        # Name: nombre de la función
        # FileName: ruta del archivo
        # HeadLines: 3 (líneas de header)
        # PreChars: 0 (sin caracteres de prefijo)
        # PointsPerLine: 1 (1 valor por línea)
        # ValueType: 1 (valores en intervalos iguales, no tiempo+valor)
        # FreeFormat: True (formato libre)
        # NumberFixed: 10 (caracteres por valor, si no es free format)
        # DT: 0.005 (intervalo de tiempo)
        
        ret = func_th.SetFromFile_1(
            name,              # Name
            filepath,          # FileName
            headLines,         # HeadLines = 3
            0,                 # PreChars = 0
            1,                 # PointsPerLine = 1
            1,                 # ValueType = 1 (equal intervals)
            True,              # FreeFormat = True
            10,                # NumberFixed = 10
            dt                 # DT = 0.005
        )
        
        if ret == 0:
            print(f"✓ Acelerograma '{name}' cargado correctamente\n")
        else:
            print(f"✗ Error: código retorno {ret}\n")
        
        return ret
    
    except AttributeError as e:
        print(f"✗ Error: SetFromFile_1 no encontrado")
        print(f"   {e}\n")
        return -1
    except Exception as e:
        print(f"✗ Error: {type(e).__name__}")
        print(f"   {e}\n")
        return -1

def list_functions(sap_model):
    """Lista las funciones time history en el modelo"""
    try:
        ret = sap_model.Func.GetNameList(2)
        
        if isinstance(ret, tuple) and len(ret) >= 3:
            count = ret[1]
            names = ret[2]
        else:
            count = 0
            names = []
        
        print(f"Funciones Time History en el modelo:")
        if count > 0:
            if isinstance(names, (list, tuple)):
                for name in names:
                    print(f"  • {name}")
            else:
                print(f"  • {names}")
        else:
            print(f"  (ninguna)")
        print()
    except Exception as e:
        print(f"Error: {e}\n")

if __name__ == "__main__":
    print("=" * 70)
    print("SAP2000 v26 - CARGAR ACELEROGRAMA")
    print("=" * 70 + "\n")
    
    try:
        # Conectar
        sap_object, sap_model = connect_to_sap2000()
        
        # Listar funciones antes
        print("Funciones antes de cargar:")
        list_functions(sap_model)
        
        # Cargar acelerograma
        acelerograma_file = r"C:\Users\rocha\Documents\ETABSlab\data\normalized\X_acc_x.txt"
        
        ret = load_accelerogram(
            sap_model,
            name="X_acc_x",
            filepath=acelerograma_file,
            headLines=3,
            dt=0.005
        )
        
        # Listar funciones después
        print("Funciones después de cargar:")
        list_functions(sap_model)
        
        # Resultado
        print("=" * 70)
        if ret == 0:
            print("✓ ¡ÉXITO! Acelerograma cargado correctamente")
            print("=" * 70)
            print("\nVerifica en SAP2000:")
            print("  Define → Functions → Time History → X_acc_x")
        else:
            print("✗ Error al cargar acelerograma")
            print("=" * 70)
    
    except Exception as e:
        print(f"Error fatal: {e}")
        import traceback
        traceback.print_exc()
