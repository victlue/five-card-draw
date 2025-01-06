async function fetchJSON(url, method="GET", data=null) {
    let opts = { method, headers: { "Content-Type": "application/json" } };
    if (data) opts.body = JSON.stringify(data);
    const resp = await fetch(url, opts);
    return await resp.json();
  }
  
  function getWhoseTurn(phase) {
    if (phase==="betting_pre_draw"||phase==="betting_post_draw"||phase==="draw_phase") return "player";
    if (phase==="computer_bet_pre_draw"||phase==="computer_bet_post_draw"||phase==="computer_draw") return "computer";
    return null;
  }
  
  // Show/hide next round button
  function updateNextRoundButton(phase){
    const btn= document.getElementById("nextRoundBtn");
    if(phase==="round_end"){
      btn.style.display="inline-block";
    } else {
      btn.style.display="none";
    }
  }
  
  // Show/hide the header
  function showHeader(show){
    const hdr= document.getElementById("header");
    hdr.style.display= show? "block":"none";
  }
  
  // Bet controls
  function updateBetControls(phase){
    const betCtrls= document.getElementById("betControls");
    const turn= getWhoseTurn(phase);
    if((phase==="betting_pre_draw"||phase==="betting_post_draw") && turn==="player"){
      betCtrls.style.display="block";
    } else {
      betCtrls.style.display="none";
    }
  }
  
  // Discard controls
  function updateDiscardControls(phase){
    const discCtrls= document.getElementById("discardControls");
    const turn= getWhoseTurn(phase);
    if(phase==="draw_phase" && turn==="player"){
      discCtrls.style.display="block";
    } else {
      discCtrls.style.display="none";
    }
  }
  
  // Show/hide bet action buttons
  function updateActionButtons(allowedActions){
    const checkBtn= document.getElementById("playerCheckBtn");
    const callBtn= document.getElementById("playerCallBtn");
    const foldBtn= document.getElementById("playerFoldBtn");
    const raiseBtn= document.getElementById("playerRaiseBtn");
  
    checkBtn.style.display="none";
    callBtn.style.display="none";
    foldBtn.style.display="none";
    raiseBtn.style.display="none";
  
    if(allowedActions.includes("check")){
      checkBtn.style.display="inline-block";
    }
    if(allowedActions.includes("call")){
      callBtn.style.display="inline-block";
    }
    if(allowedActions.includes("fold")){
      foldBtn.style.display="inline-block";
    }
    if(allowedActions.includes("bet")||allowedActions.includes("raise")){
      raiseBtn.style.display="inline-block";
    }
  }
  
  // More granular chip representation
  function renderChipPile(count, containerId){
    const cont= document.getElementById(containerId);
    cont.innerHTML="";
    // 1 chip circle ~ 2 real chips
    let chipsToShow= Math.round(count/2);
    if(count>0 && chipsToShow<1) chipsToShow=1;
  
    for(let i=0;i<chipsToShow;i++){
      const chip= document.createElement("div");
      chip.className="chip";
      cont.appendChild(chip);
    }
  }
  
  function renderGameState(state){
    if(state.phase!=="start"){
      showHeader(true);
    }
  
    // Round
    document.getElementById("roundNum").innerText= state.round;
  
    // Status
    const statusDiv= document.getElementById("status");
    statusDiv.innerText= state.message||"";
  
    // Turn highlight
    const pArea= document.getElementById("playerArea");
    const cArea= document.getElementById("computerArea");
    pArea.classList.remove("activeSide");
    cArea.classList.remove("activeSide");
  
    const turn= getWhoseTurn(state.phase);
    if(turn==="player"){
      statusDiv.innerText+=" (Player's turn)";
      pArea.classList.add("activeSide");
    } else if(turn==="computer"){
      statusDiv.innerText+=" (Computer's turn)";
      cArea.classList.add("activeSide");
    }
  
    // Chips
    document.getElementById("playerChipsNum").innerText= state.player_chips;
    document.getElementById("computerChipsNum").innerText= state.computer_chips;
    document.getElementById("pot").innerText= state.pot;
  
    renderChipPile(state.player_chips,"playerChipPile");
    renderChipPile(state.computer_chips,"computerChipPile");
    renderChipPile(state.pot,"potChipPile");
  
    // Player cards
    const pCardsDiv= document.getElementById("playerCards");
    pCardsDiv.innerHTML="";
    state.player_hand.forEach(card=>{
      const d= document.createElement("div");
      d.className="card";
      d.innerText=card;
      pCardsDiv.appendChild(d);
    });
  
    // Computer cards
    const cCardsDiv= document.getElementById("computerCards");
    cCardsDiv.innerHTML="";
    if(state.phase==="round_end"){
      // round over => reveal actual cards
      state.computer_hand.forEach(card=>{
        const d= document.createElement("div");
        d.className="card";
        d.innerText= card;
        cCardsDiv.appendChild(d);
      });
    } else {
      // show black "cards" with no text
      // e.g. 5 black squares
      for(let i=0;i< state.computer_hand.length; i++){
        const d= document.createElement("div");
        d.className="card";
        d.style.backgroundColor="#000";  // black
        d.style.color="#000";           // black text => hidden
        d.innerText="??";               // or blank
        cCardsDiv.appendChild(d);
      }
    }
  
    // Next round
    updateNextRoundButton(state.phase);
    // Bet controls
    updateBetControls(state.phase);
    // Discard controls
    updateDiscardControls(state.phase);
    // Action buttons
    updateActionButtons(state.allowed_player_actions);
  }
  
  // Start new game
  async function startGame(){
    const st= await fetchJSON("/start_game","POST");
    document.getElementById("preGame").style.display="none";
    document.getElementById("gameInterface").style.display="block";
    renderGameState(st);
    autoComputerMoveIfNeeded(st);
  }
  
  // Next round
  async function nextRound(){
    const st= await fetchJSON("/next_round","POST");
    if(st.error){
      alert(st.error);
      return;
    }
    renderGameState(st);
    autoComputerMoveIfNeeded(st);
  }
  
  // Quit game => reload page
  function quitGame(){
    window.location.reload();
  }
  
  // If it's the computer's turn, auto-do the computer action after 2s
  async function autoComputerMoveIfNeeded(state){
    const turn= getWhoseTurn(state.phase);
    if(turn==="computer"){
      setTimeout(async()=>{
        if(state.phase==="computer_draw"){
          const cSt= await fetchJSON("/computer_draw","POST");
          renderGameState(cSt);
          autoComputerMoveIfNeeded(cSt);
        }
        else if(state.phase==="computer_bet_pre_draw"||state.phase==="computer_bet_post_draw"){
          const cSt= await fetchJSON("/computer_bet","POST");
          renderGameState(cSt);
          autoComputerMoveIfNeeded(cSt);
        }
      },2000);
    }
  }
  
  // Player bet
  async function playerBet(action){
    let amt=0;
    if(action==="raise"||action==="bet"){
      const val= document.getElementById("playerRaiseAmount").value;
      amt= parseInt(val)||0;
    }
    const st= await fetchJSON("/player_bet","POST",{action, bet_amount:amt});
    if(st.error){
      alert(st.error);
      return;
    }
    renderGameState(st);
    autoComputerMoveIfNeeded(st);
  }
  
  // Player discard
  async function playerDiscard(){
    const input= document.getElementById("discardIndices").value;
    const arr= input.split(",").map(s=> parseInt(s.trim())).filter(n=>!isNaN(n));
  
    const st= await fetchJSON("/player_draw","POST",{cards_to_discard:arr});
    renderGameState(st);
    autoComputerMoveIfNeeded(st);
  }
  
  document.addEventListener("DOMContentLoaded",()=>{
    document.getElementById("startGameBtn").addEventListener("click", startGame);
    document.getElementById("nextRoundBtn").addEventListener("click", nextRound);
    document.getElementById("quitGameBtn").addEventListener("click", quitGame);
  
    document.getElementById("playerCheckBtn").addEventListener("click", ()=>playerBet("check"));
    document.getElementById("playerCallBtn").addEventListener("click", ()=>playerBet("call"));
    document.getElementById("playerFoldBtn").addEventListener("click", ()=>playerBet("fold"));
    document.getElementById("playerRaiseBtn").addEventListener("click", ()=>playerBet("raise"));
  
    document.getElementById("playerDiscardBtn").addEventListener("click", playerDiscard);
  });
  