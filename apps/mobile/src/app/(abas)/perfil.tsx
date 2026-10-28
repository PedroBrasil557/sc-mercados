import { StatusDoServidor } from "@/componentes/StatusDoServidor";
import { TelaProvisoria } from "@/componentes/TelaProvisoria";

export default function Perfil() {
  return (
    <TelaProvisoria titulo="Perfil" descricao="Casa, bairro, quem participa da lista, privacidade e exclusão de conta.">
      <StatusDoServidor />
    </TelaProvisoria>
  );
}
