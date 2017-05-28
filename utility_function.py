import re
import sys
import math
import openpyxl
import operator
from functools import reduce

class Function(object):
	def __init__(self,X,A,I,max_state=3):
		self.__regulated = X.strip()
		self.__act = re.sub('\s','',A)
		self.__inh = re.sub('\s','',I)
		self.__name_list = self.create_name_list(X.strip(),A.strip(),I.strip())
		self.__name_to_value = dict()
		self.__max_state = max_state

	def get_max_state(self):
		return self.__max_state

	def create_name_list(self,X,A,I):
		names = set([X])
		act_set = set(re.findall(r'[\w_@]+',A))
		inh_set = set(re.findall(r'[\w_@]+',I))
		return sorted(list(act_set-names)) + sorted(list(inh_set-act_set-names)) + list(names)

	def get_name_list(self):
		return self.__name_list

	def evaluate(self,states):
		self.__name_to_value.clear()
		for index in range(len(states)):
			self.__name_to_value[self.__name_list[index]] = int(states[index])
		y_act = self.eval_act(self.__act,0)
		y_inh = self.eval_inh(self.__inh)
		
		if y_act==0 and y_inh==0:
			gradient = 0
		elif y_act>y_inh:
			gradient = 1
		else:
			gradient = -1
		return sorted([0, self.__name_to_value[self.__regulated]+gradient, self.__max_state-1])[1]

	def eval_act(self,act_rule,layer):
		act_list = self.split_comma_outside_parentheses(act_rule)
		y_init = list()
		y_sum = list()

		for act_element in act_list:
			if act_element[0]=='{' and act_element[-1]=='}':
				assert(layer==0)
				y_init = self.eval_act(act_element[1:-1],1)
			elif act_element[0]=='{' and act_element[-1]==']':
				parentheses = 0
				cut_point = 0
				for index in range(len(act_element)): # Find the cut point between {} and []
					if act_element[index]=='{':
						parentheses += 1
					elif act_element[index]=='}':
						parentheses -= 1
					if parentheses==0:
						cut_point = index
						break
				y_must = self.eval_act(act_element[1:cut_point],1)
				y_enhance = self.eval_act(act_element[cut_point+2:-1],1)
				y_sum += [0 if all([y==0 for y in y_must])==True \
					else sorted([0, max(y_must)+max(y_enhance), self.__max_state-1])[1]]
			elif act_element[0]=='(' and act_element[-1]==')':
				y_and = [x \
					for and_entity in self.split_comma_outside_parentheses(act_element[1:-1]) \
					for x in self.eval_act(and_entity,1)]
				y_sum += [min(y_and)]
			else:# Single Elements
				assert(act_element.find(',')==-1)
				if act_element[-1]=='+':
					if act_element[0]=='!':
						y_sum += [int(not self.__name_to_value[act_element[1:-1]]==self.__max_state-1)]
					else:
						y_sum += [int(self.__name_to_value[act_element[:-1]]==self.__max_state-1)*2]
				elif act_element[0]=='!':
					y_sum += [int(not bool(self.__name_to_value[act_element[1:]]))]
				else:
					y_sum += [self.__name_to_value[act_element]]

		#print(act_rule + ': ' + str(y_sum))
		if layer==0:
			if self.__name_to_value[self.__regulated]==0 and len(y_init)!=0 and all([y==0 for y in y_init])==True:
				return 0
			else:
				return sum(y_init) + sum(y_sum)
		else:
			return y_sum

	def eval_inh(self,inh_rule):
		inh_list = self.split_comma_outside_parentheses(inh_rule)
		y_sum = 0

		for inh_element in inh_list:
			if inh_element[0]=='(' and inh_element[-1]==')':
				y_and = list()
				for and_entity in self.split_comma_outside_parentheses(inh_element[1:-1]):
					res = self.eval_inh(and_entity)
					if type(res) is int:
						y_and += [res]
					else:
						y_and += [self.eval_inh(and_entity)]
				y_sum += min(y_and)
			else:# Single Elements
				assert(inh_element.find(',')==-1)
				if inh_element[-1]=='+':
					if inh_element[0]=='!':
						y_sum += int(not self.__name_to_value[inh_element[1:-1]]==self.__max_state-1)
					else:
						y_sum += int(self.__name_to_value[inh_element[:-1]]==self.__max_state-1)*2
				elif inh_element[0]=='!':
					y_sum += int(not bool(self.__name_to_value[inh_element[1:]]))
				else:
					y_sum += self.__name_to_value[inh_element]

		return y_sum

	def generate_all_input_state(self,include_regulated=0): # Whether or not include the regulated element itself
		length = len(self.__name_list) if include_regulated else len(self.__name_list)-1
		total_states = []
		for num in range(int(math.pow(self.__max_state,length))):
			result = ''
			temp = num
			while temp > 0:
				result = str(temp%self.__max_state) + result
				temp = temp//self.__max_state
			total_states.append(result.zfill(length))
		return total_states

	def generate_model_expression(self,output_model_file):
		if self.__act=='' and self.__inh=='':
			return None

		else:
			input_states = self.generate_all_input_state(1)
			mode_to_expresion = [[] for x in range(math.ceil(math.log(self.__max_state,2)))]
			for state in input_states:
				value = self.evaluate(state)
				for k in range(math.ceil(math.log(value+1,2))):
					if value%2:
						mode_to_expresion[k].append('('+self.state_to_expression(state)+')')
					value = value//2

			output_model_file.write('{\n')
			for index in range(len(mode_to_expresion)):
				mode = mode_to_expresion[index]
				if len(mode)!=0:
					output_model_file.write(self.__regulated+'_'+str(index)+' = '+\
						' + '.join(mode)+';\n')
				else:
					output_model_file.write(self.__regulated+'_'+str(index)+' = Const_False;\n')
			output_model_file.write('}\n')

	def state_to_expression(self,state):
		result = list()
		for index in range(len(state)):
			element = self.__name_list[index]
			value = int(state[index])
			for k in range(math.ceil(math.log(self.__max_state,2))):
				if value%2:
					result.append(element+'_'+str(k))
				else:
					result.append('!'+element+'_'+str(k))
				value = value//2

		return '*'.join(result)

	def split_comma_outside_parentheses(self,sentence):
		final_list = list()
		parentheses = 0
		start = 0
		for index in range(len(sentence)):
			char = sentence[index]
			if index==len(sentence)-1:
				final_list.append(sentence[start:index+1])
			elif char=='(' or char=='{' or char=='[':
				parentheses += 1
			elif char==')' or char=='}' or char==']':
				parentheses -= 1
			elif (char==',' and parentheses==0):
				final_list.append(sentence[start:index])
				start = index+1
		return final_list

def main():
	
	#f = Function('X','{{(A,B)}[C,D,E]},F,G','K')
	#print(f.get_name_list())
	#print('101000011')
	#print(f.evaluate('101000011'))
	f = Function('X','{A},B','')
	f.generate_model_expression(sys.stdout)


if __name__=="__main__":
	main()