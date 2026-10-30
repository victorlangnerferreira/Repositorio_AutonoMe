let tipoContaAtual = "cliente";

        const botaoCliente = document.getElementById("btn-cliente");
        const botaoProfissional = document.getElementById("btn-profissional");
        const mensagemErro = document.getElementById("mensagem-erro");
        const campoCpf = document.getElementById("cpf");
        const campoTelefone = document.getElementById("telefone");
        const campoCodigoCadastro = document.getElementById("codigo-cadastro");
        const areaVerificacaoCadastro = document.getElementById("verificacao-cadastro");
        const botaoConfirmarCadastro = document.getElementById("btn-confirmar");
        const botaoEditarCadastro = document.getElementById("btn-editar-cadastro");
        const camposCadastro = ["nome", "email", "cpf", "telefone", "senha", "confirmar"]
            .map(id => document.getElementById(id));
        let codigoCadastroEnviado = false;

        campoCodigoCadastro.addEventListener("input", function () {
            campoCodigoCadastro.value = campoCodigoCadastro.value.replace(/[^a-z0-9]/gi, "").slice(0, 6).toUpperCase();
        });

        botaoEditarCadastro.addEventListener("click", function () {
            codigoCadastroEnviado = false;
            camposCadastro.forEach(campo => { campo.disabled = false; });
            botaoCliente.disabled = false;
            botaoProfissional.disabled = false;
            campoCodigoCadastro.value = "";
            campoCodigoCadastro.disabled = true;
            campoCodigoCadastro.required = false;
            areaVerificacaoCadastro.hidden = true;
            botaoEditarCadastro.hidden = true;
            botaoConfirmarCadastro.textContent = "Confirmar";
            mensagemErro.textContent = "Edite os dados e envie o formulário para solicitar outro código.";
            mensagemErro.style.display = "block";
        });

        function formatarCpf(valor) {
            const digitos = valor.replace(/\D/g, "").slice(0, 11);
            if (digitos.length <= 3) return digitos;
            if (digitos.length <= 6) return `${digitos.slice(0, 3)}.${digitos.slice(3)}`;
            if (digitos.length <= 9) return `${digitos.slice(0, 3)}.${digitos.slice(3, 6)}.${digitos.slice(6)}`;
            return `${digitos.slice(0, 3)}.${digitos.slice(3, 6)}.${digitos.slice(6, 9)}-${digitos.slice(9)}`;
        }

        function cpfValido(valor) {
            const cpf = valor.replace(/\D/g, "");
            if (cpf.length !== 11 || /^([0-9])\1{10}$/.test(cpf)) return false;
            for (let posicao = 9; posicao <= 10; posicao++) {
                let soma = 0;
                for (let indice = 0; indice < posicao; indice++) {
                    soma += Number(cpf[indice]) * (posicao + 1 - indice);
                }
                const resto = (soma * 10) % 11;
                const digito = resto === 10 ? 0 : resto;
                if (digito !== Number(cpf[posicao])) return false;
            }
            return true;
        }

        function formatarCelular(valor) {
            const digitos = valor.replace(/\D/g, "").slice(0, 11);
            if (digitos.length <= 2) return digitos ? `(${digitos}` : "";
            if (digitos.length <= 7) return `(${digitos.slice(0, 2)}) ${digitos.slice(2)}`;
            return `(${digitos.slice(0, 2)}) ${digitos.slice(2, 7)}-${digitos.slice(7)}`;
        }

        campoCpf.addEventListener("input", function () {
            campoCpf.value = formatarCpf(campoCpf.value);
            campoCpf.setCustomValidity(cpfValido(campoCpf.value) ? "" : "Informe um CPF válido.");
        });

        campoTelefone.addEventListener("input", function () {
            campoTelefone.value = formatarCelular(campoTelefone.value);
            const celular = campoTelefone.value.replace(/\D/g, "");
            const ddd = Number(celular.slice(0, 2));
            const valido = celular.length === 11 && ddd >= 11 && ddd <= 99 && celular[2] === "9";
            campoTelefone.setCustomValidity(valido ? "" : "Informe um celular válido com DDD.");
        });

        botaoCliente.addEventListener("click", function () {
            tipoContaAtual = "cliente";
            botaoCliente.classList.add("selecionada");
            botaoProfissional.classList.remove("selecionada");
            botaoCliente.setAttribute("aria-pressed", "true");
            botaoProfissional.setAttribute("aria-pressed", "false");
        });

        botaoProfissional.addEventListener("click", function () {
            tipoContaAtual = "profissional";
            botaoProfissional.classList.add("selecionada");
            botaoCliente.classList.remove("selecionada");
            botaoProfissional.setAttribute("aria-pressed", "true");
            botaoCliente.setAttribute("aria-pressed", "false");
        });

        document.getElementById("form-cadastro").addEventListener("submit", async function (evento) {
            evento.preventDefault();
            mensagemErro.textContent = "";
            mensagemErro.style.display = "none";

            if (codigoCadastroEnviado) {
                botaoConfirmarCadastro.disabled = true;
                try {
                    await confirmarCadastro(document.getElementById("email").value.trim(), campoCodigoCadastro.value);
                    alert("E-mail confirmado! Conta criada. Agora entre com seu e-mail e senha.");
                    window.location.href = "login.html";
                } catch (erro) {
                    mensagemErro.textContent = erro.message || "Não foi possível confirmar o código.";
                    mensagemErro.style.display = "block";
                    botaoConfirmarCadastro.disabled = false;
                }
                return;
            }

            const dados = {
                nome: document.getElementById("nome").value.trim(),
                email: document.getElementById("email").value.trim(),
                cpf: campoCpf.value,
                telefone: campoTelefone.value,
                senha: document.getElementById("senha").value,
                confirmacao_senha: document.getElementById("confirmar").value,
                tipo: tipoContaAtual,
            };

            if (dados.senha !== dados.confirmacao_senha) {
                mensagemErro.textContent = "As senhas não coincidem.";
                mensagemErro.style.display = "block";
                return;
            }

            try {
                await cadastrarPf(dados);
                codigoCadastroEnviado = true;
                areaVerificacaoCadastro.hidden = false;
                campoCodigoCadastro.disabled = false;
                campoCodigoCadastro.required = true;
                botaoEditarCadastro.hidden = false;
                camposCadastro.forEach(campo => { campo.disabled = true; });
                botaoCliente.disabled = true;
                botaoProfissional.disabled = true;
                botaoConfirmarCadastro.textContent = "Verificar e criar conta";
                mensagemErro.textContent = "Enviamos um código de 6 caracteres para seu e-mail. Ele expira em 10 minutos.";
                mensagemErro.style.display = "block";
            } catch (erro) {
                const textoErro = erro && typeof erro.message === "string" ? erro.message : "";
                mensagemErro.textContent = textoErro === "[object Object]"
                    ? "Reinicie a API e tente novamente."
                    : textoErro || "Não foi possível criar a conta.";
                mensagemErro.style.display = "block";
            }
        });