import { Route,Routes } from 'react-router-dom'
import './App.css'
import Home from './pages/Home'
import Login from './pages/Login'
import Registration from './pages/Registration'
import Account from './pages/Account'

export default function App() {


  return (
    <>
      <Routes>
        <Route path='/' element={<Home />}/>
        <Route path='/Login' element={<Login />}/>
        <Route path='/Registration' element={<Registration />}/>
        <Route path='/Account' element={<Account />}/>
      </Routes>
    </>
  )
}

