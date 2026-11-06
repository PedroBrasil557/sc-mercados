/**
 * Modo de teste: fotos dos produtos e logos dos mercados, que são das redes e dos fabricantes e ainda não têm
 * autorização para ir a público. Ligado no Expo Go (desenvolvimento) e no APK de teste do perfil "preview" do EAS
 * (EXPO_PUBLIC_MODO_TESTE=1 em eas.json). A versão de loja (perfil "production") não liga e mostra a miniatura.
 */
export const MODO_TESTE = __DEV__ || process.env.EXPO_PUBLIC_MODO_TESTE === "1";
